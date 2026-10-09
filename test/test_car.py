import json
import zipfile

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.car import car_fingerprint, pack_car
from test.car_fixtures import car_bytes


@pytest.mark.parametrize('bands,opaque', [(False, False), (True, False), (False, True)])
def test_car_preserves_all_blocks_metadata_bands_and_opaque_resources(tmp_path, bands, opaque):
    source = tmp_path / 'catalog.car'
    original = car_bytes(bands, opaque)
    source.write_bytes(original)
    result = pack_car(str(source))
    assert result.replaced and source.stat().st_size < len(original)
    assert car_fingerprint(original) == car_fingerprint(source.read_bytes())


@pytest.mark.parametrize('mode', ['dryrun', 'output', 'backup', 'minimum'])
def test_car_publication_policies(tmp_path, mode):
    source, output = tmp_path / 'catalog.car', tmp_path / 'output.car'
    original = car_bytes()
    source.write_bytes(original)
    result = FileRepacker().repack(str(source), outfile=str(output) if mode == 'output' else None,
        options=RepackOptions(dryrun=mode == 'dryrun', backup=mode == 'backup',
                              min_savings=100 if mode == 'minimum' else None))
    if mode in ('dryrun', 'output', 'minimum'):
        assert source.read_bytes() == original
    if mode == 'output':
        assert result.published
        assert car_fingerprint(output.read_bytes()) == car_fingerprint(original)
    if mode == 'backup':
        assert (tmp_path / 'catalog.car.bak').read_bytes() == original


@pytest.mark.parametrize('failure', ['decoded', 'memory', 'nodes', 'scratch', 'invalid'])
def test_car_refusal_preserves_input_and_destination(tmp_path, failure):
    source, output = tmp_path / 'catalog.car', tmp_path / 'output.car'
    original = car_bytes()[:-8] if failure == 'invalid' else car_bytes()
    source.write_bytes(original)
    output.write_bytes(b'prior destination')
    option = 'format_max_nodes' if failure == 'nodes' else 'format_max_' + failure + '_bytes'
    options = {'overwrite': True, **({option: 1} if failure != 'invalid' else {})}
    result = FileRepacker().repack(str(source), outfile=str(output), options=options)
    assert source.read_bytes() == original and output.read_bytes() == b'prior destination'
    assert result.outcome.status == ('failed' if failure == 'invalid' else 'skipped')


@pytest.mark.parametrize('command', ['repack', 'bulk'])
def test_car_cli_and_bulk(tmp_path, command):
    source = tmp_path / 'catalog.car'
    source.write_bytes(car_bytes())
    result = CliRunner().invoke(app, [command, str(source if command == 'repack' else tmp_path),
                                     '--json'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)['files'][0]['status'] == 'replaced'


def test_car_nested_archive(tmp_path):
    source = tmp_path / 'catalog.zip'
    original = car_bytes(True)
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('catalog.car', original)
    result = FileRepacker().repack(str(source))
    assert result.outcome.status == 'replaced'
    with zipfile.ZipFile(source) as archive:
        assert car_fingerprint(archive.read('catalog.car')) == car_fingerprint(original)
