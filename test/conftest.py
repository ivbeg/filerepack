# -*- coding: utf-8 -*-

import os
import tempfile
import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_text_file(temp_dir):
    """Create a small sample text file."""
    filepath = os.path.join(temp_dir, 'sample.txt')
    with open(filepath, 'w') as f:
        f.write('Hello, World! ' * 100)
    return filepath


@pytest.fixture
def sample_gz_file(temp_dir):
    """Create a small sample gzip file."""
    import gzip
    filepath = os.path.join(temp_dir, 'sample.txt.gz')
    with gzip.open(filepath, 'wt') as f:
        f.write('Hello, World! ' * 100)
    return filepath


@pytest.fixture
def sample_bz2_file(temp_dir):
    """Create a small sample bz2 file."""
    import bz2
    filepath = os.path.join(temp_dir, 'sample.txt.bz2')
    with bz2.open(filepath, 'wt') as f:
        f.write('Hello, World! ' * 100)
    return filepath


@pytest.fixture
def sample_xz_file(temp_dir):
    """Create a small sample xz file."""
    import lzma
    filepath = os.path.join(temp_dir, 'sample.txt.xz')
    with lzma.open(filepath, 'wt') as f:
        f.write('Hello, World! ' * 100)
    return filepath


@pytest.fixture
def sample_zip_file(temp_dir):
    """Create a small sample ZIP file."""
    import zipfile
    filepath = os.path.join(temp_dir, 'sample.zip')
    with zipfile.ZipFile(filepath, 'w') as zf:
        zf.writestr('test.txt', 'Hello, World! ' * 100)
    return filepath
