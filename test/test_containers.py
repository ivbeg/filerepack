# -*- coding: utf-8 -*-

import os
from unittest.mock import patch

from filerepack.containers import (
    MemberResult, pack_members, shrunken_paths, staging_dir,
)


class TestStagingDir:
    def test_creates_and_cleans(self):
        with staging_dir() as path:
            assert os.path.isdir(path)
            marker = os.path.join(path, 'a.txt')
            with open(marker, 'w') as fh:
                fh.write('x')
            saved = path
        assert not os.path.exists(saved)

    def test_cleans_on_exception(self):
        saved = None
        try:
            with staging_dir() as path:
                saved = path
                raise RuntimeError('boom')
        except RuntimeError:
            pass
        assert saved is not None
        assert not os.path.exists(saved)


class TestPackMembers:
    def test_noop_when_packer_returns_none(self, tmp_path):
        path = tmp_path / 'a.jpg'
        payload = b'\xff\xd8\xff' + b'\x00' * 32
        path.write_bytes(payload)
        with patch('filerepack.repack._dispatch_packer', return_value=None):
            results = pack_members({'cover': str(path)})
        item = results['cover']
        assert item.shrank is False
        assert item.packed is False
        assert path.read_bytes() == payload

    def test_shrunken_paths(self, tmp_path):
        small = tmp_path / 'small.png'
        small.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 8)

        def fake_dispatch(ext, fullname, options):
            with open(fullname, 'wb') as fh:
                fh.write(b'\x89PNG\r\n\x1a\n')
            from filerepack.models import PackResult
            return PackResult(fullname, 20, 8, 60.0)

        with patch('filerepack.repack._dispatch_packer', side_effect=fake_dispatch):
            results = pack_members({'img': str(small)})
        assert results['img'].shrank is True
        assert shrunken_paths(results) == {'img': str(small)}

    def test_member_result_shrank(self):
        assert MemberResult('a', '/a', 10, 8, True).shrank is True
        assert MemberResult('a', '/a', 10, 10, True).shrank is False
