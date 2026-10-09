import sys
import time

import pytest

from filerepack import RepackOptions
from filerepack.commands import capture_prefix
from filerepack.format_support import Budget, FormatLimits, FormatLimit
from filerepack.resource_slots import reserve_slots


def test_stalled_prefix_has_a_deadline_and_kills_owned_descendants(tmp_path):
    import psutil
    path = tmp_path / 'child.pid'
    script = ('import subprocess,sys,time; '
              'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]); '
              'open(sys.argv[1],"w").write(str(p.pid));time.sleep(60)')
    started = time.monotonic()
    with pytest.raises(Exception, match='timed out|time budget'):
        capture_prefix([sys.executable, '-c', script, str(path)], timeout=0.5)
    assert time.monotonic() - started < 3
    if path.exists():
        pid = int(path.read_text())
        assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_prefix_stops_an_unbounded_producer():
    script = 'import sys\nwhile True:\n sys.stdout.buffer.write(bytes([120])*65536)\n'
    result = capture_prefix([sys.executable, '-c',
                             script])
    assert result == b'x' * 512


def test_aggregate_bulk_backpressure_and_oversized_grant():
    options = RepackOptions(format_max_memory_bytes=100, format_max_scratch_bytes=1000,
                             tool_threads=2)
    grant = reserve_slots(8, options, memory=300, scratch=2000, cpu=8)
    assert grant.granted == 2
    assert grant.granted * options.format_max_memory_bytes <= grant.memory_bytes
    assert grant.granted * options.format_max_scratch_bytes <= grant.scratch_bytes
    with pytest.raises(ValueError, match='exceeds'):
        reserve_slots(8, options, memory=99, scratch=2000, cpu=8)


def test_depth_is_a_separate_security_limit():
    budget = Budget(FormatLimits(depth=2))
    budget.depth(2)
    with pytest.raises(FormatLimit, match='nesting depth'):
        budget.depth(3)


@pytest.mark.parametrize('codec', ['gz', 'bz2', 'xz'])
def test_stream_decode_bomb_and_validation_share_the_root_budget(tmp_path, codec):
    import bz2
    import gzip
    import lzma
    from filerepack import FileRepacker
    source = tmp_path / ('bomb.' + codec)
    raw = b'x' * 1000000
    source.write_bytes({'gz': gzip.compress, 'bz2': bz2.compress, 'xz': lzma.compress}[codec](raw))
    original = source.read_bytes()
    output = tmp_path / ('output.' + codec)
    summary = FileRepacker().repack(str(source), str(output),
                                    RepackOptions(format_max_decoded_bytes=10000))
    assert summary.outcome.status == 'skipped'
    assert summary.outcome.reason_code == 'resource_limit'
    assert source.read_bytes() == original and not output.exists()
