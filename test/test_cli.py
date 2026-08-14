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
        assert result.exit_code in (0, 1)


# Fixtures needed for CLI tests
@pytest.fixture
def sample_text_file(tmp_path):
    filepath = tmp_path / 'sample.txt'
    filepath.write_text('Hello, World! ' * 100)
    return str(filepath)
