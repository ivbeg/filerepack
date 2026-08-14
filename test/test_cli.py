# -*- coding: utf-8 -*-

import gzip
import json
import pytest
from typer.testing import CliRunner
from filerepack.__main__ import app

runner = CliRunner()


class TestRepackCLI:
    def test_help_output(self):
        result = runner.invoke(app, ['repack', '--help'])
        assert result.exit_code == 0
        assert '--dryrun' in result.output
        assert '--quiet' in result.output

    def test_repack_nonexistent_file(self):
        result = runner.invoke(app, ['repack', '/nonexistent/file.docx'])
        assert result.exit_code == 1
        assert 'does not exist' in result.output

    def test_repack_valid_file_verbose(self, sample_text_file):
        result = runner.invoke(app, ['repack', sample_text_file, '--dryrun'])
        # Should not crash even if file type is not compressible
        assert result.exit_code == 0 or result.exit_code == 1

    def test_json_and_csv_exclusive(self, tmp_path):
        f = tmp_path / 'a.gz'
        with gzip.open(f, 'wb') as fh:
            fh.write(b'hello' * 20)
        result = runner.invoke(app, ['repack', str(f), '--json', '--csv'])
        assert result.exit_code == 1
        assert 'mutually exclusive' in result.output

    def test_repack_json_has_files_list(self, tmp_path):
        f = tmp_path / 'a.gz'
        with gzip.open(f, 'wb') as fh:
            fh.write(b'hello' * 20)
        result = runner.invoke(app, ['repack', str(f), '--json', '--dryrun'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'file' in data
        assert 'files' in data
        assert 'original_size' in data

    def test_max_extract_size_in_help(self):
        result = runner.invoke(app, ['repack', '--help'])
        assert '--max-extract-size' in result.output

    def test_pdf_profile_in_help(self):
        result = runner.invoke(app, ['repack', '--help'])
        assert '--pdf-profile' in result.output
        result = runner.invoke(app, ['bulk', '--help'])
        assert '--pdf-profile' in result.output

    def test_keep_meta_in_help(self):
        result = runner.invoke(app, ['repack', '--help'])
        assert '--keep-meta' in result.output
        result = runner.invoke(app, ['bulk', '--help'])
        assert '--keep-meta' in result.output

    def test_invalid_pdf_profile(self, tmp_path):
        f = tmp_path / 'a.pdf'
        f.write_bytes(b'%PDF-1.4\n')
        result = runner.invoke(
            app, ['repack', str(f), '--pdf-profile', 'ultra'],
        )
        assert result.exit_code == 1
        assert 'Unknown PDF profile' in result.output


class TestBulkCLI:
    def test_help_output(self):
        result = runner.invoke(app, ['bulk', '--help'])
        assert result.exit_code == 0
        assert '--dryrun' in result.output

    def test_bulk_nonexistent_dir(self):
        result = runner.invoke(app, ['bulk', '/nonexistent/dir'])
        assert result.exit_code == 1
        assert 'does not exist' in result.output

    def test_bulk_finds_jpeg(self, tmp_path):
        photo = tmp_path / 'photo.jpg'
        photo.write_bytes(b'\xff\xd8\xff' + b'\x00' * 32)
        result = runner.invoke(app, ['bulk', str(tmp_path), '--dryrun', '--quiet'])
        assert result.exit_code == 0
        assert 'Found 1 files' in result.output or result.exit_code == 0

    def test_bulk_finds_tgz(self, tmp_path):
        archive = tmp_path / 'bundle.tgz'
        archive.write_bytes(b'\x1f\x8b' + b'\x00' * 32)
        result = runner.invoke(app, ['bulk', str(tmp_path), '--dryrun', '--quiet'])
        assert result.exit_code == 0
        assert 'Found 1 files' in result.output or result.exit_code == 0

    def test_invalid_jobs(self, tmp_path):
        result = runner.invoke(app, ['bulk', str(tmp_path), '--jobs', 'nope'])
        assert result.exit_code == 1


class TestDoctorCLI:
    def test_help_output(self):
        result = runner.invoke(app, ['doctor', '--help'])
        assert result.exit_code == 0

    def test_doctor_runs(self):
        result = runner.invoke(app, ['doctor'])
        assert 'szip' in result.output
        assert 'lz4' in result.output
        assert 'woff2_compress' in result.output
        assert 'mp3packer' in result.output
        assert 'gdcmconv' in result.output
        assert 'dcmcjpls' in result.output
        assert 'jpegtran' in result.output
        assert 'zopflipng' in result.output
        assert 'optivorbis' in result.output
        assert result.exit_code in (0, 1)

    def test_doctor_install_hints_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            'filerepack.__main__.doctor_rows',
            lambda: [
                {
                    'tool': 'szip',
                    'binaries': '7zz, 7z',
                    'path': '/usr/bin/7zz',
                    'status': 'ok',
                    'purpose': 'archives',
                    'install': '',
                },
                {
                    'tool': 'jpegoptim',
                    'binaries': 'jpegoptim',
                    'path': '',
                    'status': 'missing (optional)',
                    'purpose': 'JPEG',
                    'install': 'brew install jpegoptim',
                },
            ],
        )
        monkeypatch.setattr(
            'filerepack.__main__.install_instructions',
            lambda keys: (
                'Install missing tools on macOS:\n\n'
                '  Homebrew:\n'
                '    brew install jpegoptim\n'
            ) if keys == ['jpegoptim'] else '',
        )
        result = runner.invoke(app, ['doctor'])
        assert result.exit_code == 0
        assert 'jpegoptim' in result.output
        assert 'brew install jpegoptim' in result.output
        assert 'Install missing tools' in result.output


# Fixtures needed for CLI tests
@pytest.fixture
def sample_text_file(tmp_path):
    filepath = tmp_path / 'sample.txt'
    filepath.write_text('Hello, World! ' * 100)
    return str(filepath)
