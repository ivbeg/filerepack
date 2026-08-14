# -*- coding: utf-8 -*-

import os
from filerepack.utils import (
    parse_size, format_size, parse_extensions, should_process_file,
    create_backup, output_json, output_csv,
    parse_jobs, parse_dir_names, DEFAULT_EXCLUDE_DIRS,
    dir_total_size, extract_exceeds_limit, zip_uncompressed_size,
)


class TestParseSize:
    def test_bytes(self):
        assert parse_size('100') == 100

    def test_kilobytes(self):
        assert parse_size('1KB') == 1024

    def test_megabytes(self):
        assert parse_size('1MB') == 1048576

    def test_gigabytes(self):
        assert parse_size('2GB') == 2 * 1024 ** 3

    def test_terabytes(self):
        assert parse_size('1TB') == 1024 ** 4

    def test_decimal(self):
        assert parse_size('1.5KB') == int(1.5 * 1024)

    def test_empty_string(self):
        assert parse_size('') == 0

    def test_none(self):
        assert parse_size(None) == 0

    def test_plain_number(self):
        assert parse_size('1000') == 1000


class TestFormatSize:
    def test_bytes(self):
        result = format_size(100)
        assert '100.00 B' == result

    def test_kilobytes(self):
        result = format_size(1024)
        assert '1.00 KB' == result

    def test_megabytes(self):
        result = format_size(1048576)
        assert '1.00 MB' == result

    def test_gigabytes(self):
        result = format_size(1073741824)
        assert '1.00 GB' == result


class TestParseExtensions:
    def test_single_extension(self):
        assert parse_extensions('docx') == ['docx']

    def test_multiple_extensions(self):
        assert parse_extensions('docx,xlsx,pptx') == ['docx', 'xlsx', 'pptx']

    def test_with_dots(self):
        assert parse_extensions('.docx,.xlsx') == ['docx', 'xlsx']

    def test_with_spaces(self):
        assert parse_extensions('docx, xlsx , pptx') == ['docx', 'xlsx', 'pptx']

    def test_empty_string(self):
        assert parse_extensions('') == []

    def test_none(self):
        assert parse_extensions(None) == []


class TestShouldProcessFile:
    def test_passes_without_filters(self, sample_text_file):
        should_process, reason = should_process_file(sample_text_file)
        assert should_process is True
        assert reason == ""

    def test_exclude_extension(self, sample_text_file):
        should_process, reason = should_process_file(
            sample_text_file, exclude_exts=['txt']
        )
        assert should_process is False
        assert 'exclude list' in reason

    def test_include_extension_matching(self, sample_text_file):
        should_process, reason = should_process_file(
            sample_text_file, include_exts=['txt', 'docx']
        )
        assert should_process is True

    def test_include_extension_not_matching(self, sample_text_file):
        should_process, reason = should_process_file(
            sample_text_file, include_exts=['docx']
        )
        assert should_process is False
        assert 'not in include list' in reason

    def test_min_size_filter(self, sample_text_file):
        should_process, reason = should_process_file(
            sample_text_file, min_size=1
        )
        assert should_process is True

    def test_max_size_filter(self, sample_text_file):
        should_process, reason = should_process_file(
            sample_text_file, max_size=999999999
        )
        assert should_process is True

    def test_max_size_exceeded(self, sample_text_file):
        should_process, reason = should_process_file(
            sample_text_file, max_size=1
        )
        assert should_process is False
        assert 'max_size' in reason

    def test_include_compound_tar_gz(self, tmp_path):
        path = tmp_path / 'a.tar.gz'
        path.write_bytes(b'\x1f\x8b' + b'\x00' * 8)
        should, _reason = should_process_file(str(path), include_exts=['tar.gz'])
        assert should is True
        should, _reason = should_process_file(str(path), include_exts=['gz'])
        assert should is True
        should, _reason = should_process_file(str(path), include_exts=['jpg'])
        assert should is False


class TestCreateBackup:
    def test_create_backup_same_dir(self, sample_text_file):
        backup_path = create_backup(sample_text_file)
        assert backup_path is not None
        assert backup_path.endswith('.bak')
        assert os.path.exists(backup_path)
        # Cleanup
        os.remove(backup_path)

    def test_create_backup_custom_dir(self, sample_text_file, temp_dir):
        backup_dir = os.path.join(temp_dir, 'backups')
        backup_path = create_backup(sample_text_file, backup_dir)
        assert backup_path is not None
        assert os.path.exists(backup_path)
        assert 'backups' in backup_path
        # Cleanup
        os.remove(backup_path)


class TestOutputJson:
    def test_output_to_stdout(self, capsys):
        data = {'result': 'success', 'size': 100}
        output_json(data)
        captured = capsys.readouterr()
        assert '"success"' in captured.out
        assert '100' in captured.out

    def test_output_to_file(self, temp_dir):
        output_file = os.path.join(temp_dir, 'output.json')
        data = {'result': 'success'}
        output_json(data, output_file)
        assert os.path.exists(output_file)
        with open(output_file) as f:
            content = f.read()
            assert 'success' in content


class TestOutputCsv:
    def test_output_with_valid_data(self, capsys):
        data = {'files': [['file1.txt', 100, 80, 20.0]]}
        output_csv(data)
        captured = capsys.readouterr()
        assert 'file1.txt' in captured.out
        assert '100' in captured.out

    def test_output_with_no_files(self, capsys):
        data = {'files': []}
        output_csv(data)
        captured = capsys.readouterr()
        assert captured.out == ''

    def test_output_with_dict_rows(self, capsys):
        data = {'files': [{
            'file': 'a.docx',
            'original_size': 100,
            'final_size': 80,
            'savings_percent': 20.0,
            'savings_bytes': 20,
        }]}
        output_csv(data)
        captured = capsys.readouterr()
        assert 'a.docx' in captured.out
        assert '100' in captured.out


class TestParseJobs:
    def test_numeric(self):
        assert parse_jobs('4') == 4

    def test_auto(self):
        assert parse_jobs('auto') >= 1


class TestParseDirNames:
    def test_comma_separated(self):
        assert parse_dir_names('.git,node_modules') == {'.git', 'node_modules'}

    def test_defaults_include_git(self):
        assert '.git' in DEFAULT_EXCLUDE_DIRS


class TestExtractLimits:
    def test_none_is_not_over(self):
        assert extract_exceeds_limit(None, 100, 8 * 1024 ** 3, 100.0) is False

    def test_byte_cap(self):
        assert extract_exceeds_limit(101, 50, 100, 100.0) is True
        assert extract_exceeds_limit(50, 50, 100, 100.0) is False

    def test_ratio(self):
        assert extract_exceeds_limit(10001, 100, 10 ** 12, 100.0) is True
        assert extract_exceeds_limit(5000, 100, 10 ** 12, 100.0) is False

    def test_unlimited(self):
        assert extract_exceeds_limit(10 ** 12, 1, 0, 0.0) is False


class TestZipUncompressedSize:
    def test_sums_entries(self, tmp_path):
        path = tmp_path / 'a.zip'
        import zipfile
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('a.txt', 'a' * 10)
            zf.writestr('b.txt', 'b' * 5)
        assert zip_uncompressed_size(str(path)) == 15

    def test_non_zip(self, tmp_path):
        path = tmp_path / 'a.bin'
        path.write_bytes(b'nope')
        assert zip_uncompressed_size(str(path)) is None


class TestDirTotalSize:
    def test_nested(self, tmp_path):
        (tmp_path / 'a.txt').write_bytes(b'abc')
        sub = tmp_path / 'sub'
        sub.mkdir()
        (sub / 'b.txt').write_bytes(b'de')
        assert dir_total_size(str(tmp_path)) == 5
