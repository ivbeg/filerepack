"""Build and validate release artifacts without importing the checkout."""

import argparse
import configparser
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath


def run(command, *, cwd, capture=False):
    display = [str(arg) for arg in command]
    if '-c' in display:
        display[display.index('-c') + 1] = '<validation code>'
    print('+', ' '.join(display), flush=True)
    try:
        return subprocess.run(command, cwd=cwd, check=True, text=True,
                              capture_output=capture)
    except subprocess.CalledProcessError as exc:
        if capture:
            print((exc.stdout or '') + (exc.stderr or ''), file=sys.stderr)
        raise


def license_metadata(data):
    metadata = Parser().parsestr(data.decode('utf-8'))
    if metadata['Name'] != 'filerepack' or metadata['License-Expression'] != 'BSD-3-Clause':
        raise ValueError('artifact must declare filerepack with License-Expression: BSD-3-Clause')
    if 'LICENSE' not in metadata.get_all('License-File', []):
        raise ValueError('artifact must declare its LICENSE file')
    return metadata['Version']


def runtime_sources(project):
    return {path.relative_to(project).as_posix() for path in (project / 'filerepack').rglob('*.py')
            if '__pycache__' not in path.parts}


def check_source(archive, project, destination):
    required = {path.relative_to(project).as_posix() for path in (project / 'test').rglob('*')
                if path.is_file() and '__pycache__' not in path.parts
                and path.suffix not in ('.pyc', '.pyo', '.pyd') and path.name != '.DS_Store'}
    required.update({'pyproject.toml', 'setup.py', 'MANIFEST.in', '.coveragerc',
                     'LICENSE', 'README.md', 'CONTRIBUTING.md', 'CHANGELOG.md',
                     'dev/validate_distribution.py'})
    required.update({'tools/ole-compactor/Cargo.toml', 'tools/ole-compactor/Cargo.lock',
                     'tools/ole-compactor/src/main.rs', 'tools/ole-compactor/README.md',
                     'tools/ole-compactor/LICENSE', 'tools/ole-compactor/THIRD_PARTY_LICENSES.md'})
    required.update(runtime_sources(project))
    with tarfile.open(archive) as source:
        members = source.getmembers()
        roots = {PurePosixPath(member.name).parts[0] for member in members}
        if len(roots) != 1:
            raise ValueError('sdist must contain exactly one project root')
        root = roots.pop()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir()):
                raise ValueError('unsafe or unsupported source artifact member: ' + member.name)
        present = {member.name[len(root) + 1:] for member in members if member.isfile()}
        missing = required - present
        if missing:
            raise ValueError('sdist missing required files: ' + ', '.join(sorted(missing)))
        metadata = source.extractfile(root + '/PKG-INFO')
        if metadata is None:
            raise ValueError('missing source metadata')
        version = license_metadata(metadata.read())
        license_file = source.extractfile(root + '/LICENSE')
        if license_file is None or license_file.read() != (project / 'LICENSE').read_bytes():
            raise ValueError('sdist changed license text')
        # All paths/types were checked above, including on Python 3.9.
        if hasattr(tarfile, 'data_filter'):
            source.extractall(destination, filter='data')
        else:
            source.extractall(destination)
    return destination / root, version


def check_wheel(archive, project, version):
    with zipfile.ZipFile(archive) as wheel:
        names = wheel.namelist()
        missing = runtime_sources(project) - set(names)
        if missing:
            raise ValueError('wheel missing runtime modules: ' + ', '.join(sorted(missing)))
        for name in names:
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith('/') or '..' in parts
                    or parts[0] != 'filerepack' and not parts[0].endswith('.dist-info')):
                raise ValueError('non-runtime wheel member: ' + name)
            if any(part in ('test', 'tests', 'dev', '__pycache__') for part in parts):
                raise ValueError('test/development support leaked into runtime wheel: ' + name)
        metadata_names = [name for name in names if name.endswith('.dist-info/METADATA')]
        if len(metadata_names) != 1:
            raise ValueError('wheel must contain exactly one metadata record')
        metadata_name = metadata_names[0]
        if license_metadata(wheel.read(metadata_name)) != version:
            raise ValueError('wheel and sdist versions differ')
        info = metadata_name.rsplit('/', 1)[0]
        if wheel.read(info + '/licenses/LICENSE') != (project / 'LICENSE').read_bytes():
            raise ValueError('wheel changed license text')
        entry_points = configparser.ConfigParser()
        entry_points.read_string(wheel.read(info + '/entry_points.txt').decode())
        if entry_points.get('console_scripts', 'filerepack') != 'filerepack.__main__:main':
            raise ValueError('missing or changed filerepack console entry point')


_SMOKE = '''
import importlib.metadata, json, pathlib, sys
import filerepack
from filerepack import FileRepacker, PackResult, RepackOptions, RepackSummary
location = pathlib.Path(filerepack.__file__).resolve()
if not location.is_relative_to(pathlib.Path(sys.prefix).resolve()):
    raise RuntimeError('runtime import escaped the fresh artifact environment: ' + str(location))
if filerepack.__version__ != importlib.metadata.version('filerepack'):
    raise RuntimeError('runtime/artifact version mismatch')
if filerepack.__license__ != 'BSD-3-Clause':
    raise RuntimeError('runtime license mismatch')
if not {'FileRepacker', 'PackResult', 'RepackOptions', 'RepackSummary', '__version__'}.issubset(
        filerepack.__all__):
    raise RuntimeError('missing public package exports')
source = pathlib.Path('input.json')
original = b' { "n": 1.234567890123456789, "same": 1, "same": 2 } '
source.write_bytes(original)
output = pathlib.Path('output.json')
rp = FileRepacker()
dry = rp.repack(str(source), outfile=str(output), options=RepackOptions(dryrun=True))
if output.exists() or not dry.total_outsize < dry.total_insize:
    raise RuntimeError('installed dry-run failed')
result = rp.repack(str(source), outfile=str(output))
expected = b'{"n":1.234567890123456789,"same":1,"same":2}'
if source.read_bytes() != original or output.read_bytes() != expected:
    raise RuntimeError('installed repacker changed the preservation contract')
if not result.total_outsize < result.total_insize:
    raise RuntimeError('installed repacker did not accept the smaller candidate')
print(json.dumps({'runtime': str(location), 'version': filerepack.__version__,
                  'exports': True, 'preservation': True, 'dry_run': True}))
'''

_PYTEST = '''
import pathlib, sys
sys.path.insert(0, str(pathlib.Path.cwd()))
import filerepack, test, pytest
if not pathlib.Path(filerepack.__file__).resolve().is_relative_to(
        pathlib.Path(sys.prefix).resolve()):
    raise RuntimeError('tests imported runtime from outside the artifact environment')
if pathlib.Path(test.__file__).resolve().parent != pathlib.Path.cwd() / 'test':
    raise RuntimeError('tests imported helpers from outside the extracted source suite')
print('Artifact runtime:', filerepack.__file__, flush=True)
print('Source test support:', test.__file__, flush=True)
sys.exit(pytest.main(sys.argv[1:]))
'''


def validate_install(artifact, kind, workspace, test_root):
    environment = workspace / (kind + '-venv')
    venv.EnvBuilder(with_pip=True).create(environment)
    scripts = environment / ('Scripts' if os.name == 'nt' else 'bin')
    python = scripts / ('python.exe' if os.name == 'nt' else 'python')
    run([python, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check', 'install',
         '--no-user', '--quiet', str(artifact) + '[dev,ole-recompress]'], cwd=workspace)
    smoke_root = workspace / (kind + '-smoke')
    smoke_root.mkdir()
    run([python, '-I', '-c', _SMOKE], cwd=smoke_root)
    cli = scripts / ('filerepack.exe' if os.name == 'nt' else 'filerepack')
    for command in ([python, '-I', '-m', 'filerepack', '--help'],
                    [cli, '--help'], [cli, 'repack', '--help'], [cli, 'bulk', '--help']):
        run(command, cwd=smoke_root, capture=True)
    if kind == 'sdist':
        run([python, '-I', '-c', _PYTEST, '--collect-only', '-q'], cwd=test_root, capture=True)
        run([python, '-I', '-c', _PYTEST, '-q'], cwd=test_root)
    else:
        run([python, '-I', '-c', _PYTEST, '-q', 'test/test_models.py',
             'test/test_cli.py', 'test/test_progress.py',
             'test/test_audit_evidence.py', 'test/test_reports_resume.py',
             'test/test_planning.py', 'test/test_model_format_inspection.py',
             'test/test_bulk_lifecycle.py',
             'test/test_packer_boundaries.py', 'test/test_structural_validation.py',
             'test/test_pdf_validation.py', 'test/test_audited_formats.py',
             'test/test_ole.py', 'test/test_ole_protection.py', 'test/test_ole_ppt.py',
             'test/test_ole_ppt_notes.py', 'test/test_ole_ppt_roundtrip.py',
             'test/test_ole_ppt_animation.py', 'test/test_ole_ppt_fly_animation.py',
             'test/test_ole_png_refilter.py',
             'test/test_ole_recompress.py', 'test/test_ole_diagnostics.py',
             'test/test_ole_officeart.py', 'test/test_ole_raster.py',
             'test/test_ole_extended.py', 'test/test_ole_host_coverage.py',
             'test/test_ole_hwp_codecs.py'],
            cwd=test_root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path,
                        help='validate existing artifacts instead of building')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='filerepack-distribution-') as temporary:
        workspace = Path(temporary).resolve()
        artifacts = args.artifacts.resolve() if args.artifacts else workspace / 'artifacts'
        if args.artifacts is None:
            # The default build makes the wheel from the newly built sdist.
            run([sys.executable, '-m', 'build', '--outdir', artifacts], cwd=project, capture=True)
        sources, wheels = list(artifacts.glob('*.tar.gz')), list(artifacts.glob('*.whl'))
        if len(sources) != 1 or len(wheels) != 1:
            raise ValueError('expected exactly one sdist and one wheel')
        extracted, version = check_source(sources[0], project, workspace / 'source')
        check_wheel(wheels[0], project, version)
        # Copy only test support/config: application imports must use the installation.
        test_root = workspace / 'source-tests'
        test_root.mkdir()
        shutil.copytree(extracted / 'test', test_root / 'test')
        for name in ('pyproject.toml', '.coveragerc'):
            shutil.copy2(extracted / name, test_root / name)
        validate_install(wheels[0], 'wheel', workspace, test_root)
        validate_install(sources[0], 'sdist', workspace, test_root)
        print('Distribution validation passed (wheel and sdist installations).', flush=True)


if __name__ == '__main__':
    main()
