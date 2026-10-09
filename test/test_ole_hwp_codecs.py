"""HWP framing qualification for the optional pinned Zopfli zlib interface."""

import struct
import zlib

import pytest

from filerepack import ole_officeart
from filerepack.format_support import FormatLimit
from filerepack.ole_hwp import HwpLayout, ZOPFLI_CUTOFF, decode_stream, qualified_zopfli_raw
from filerepack.ole_verify import CompoundFile
from test.ole_art_fixtures import container
from test.test_ole_extended import budget, inspect_hwp, weak_hwp


@pytest.mark.parametrize(
    "fault", ("truncated", "header", "dictionary", "checksum", "trailing", "concat", "collision")
)
def test_optional_hwp_rejects_wrong_zlib_frame_even_with_matching_checksum(fault):
    raw = b"\x00\x02\x00" * 200
    framed = zlib.compress(raw)
    if fault == "truncated":
        framed = framed[:5]
    elif fault == "header":
        framed = b"\x88" + framed[1:]
    elif fault == "dictionary":
        encoder = zlib.compressobj(zdict=b"dictionary")
        framed = encoder.compress(raw) + encoder.flush()
    elif fault == "checksum":
        framed = framed[:-1] + bytes([framed[-1] ^ 1])
    elif fault == "trailing":
        framed += framed[-4:]
    elif fault == "concat":
        framed += framed
    else:
        different = b"\x01\x00\x01" * 200
        assert raw != different and zlib.adler32(raw) == zlib.adler32(different)
        framed = zlib.compress(different)
    with pytest.raises(ValueError):
        qualified_zopfli_raw(framed, raw, budget())


def test_hwp_optional_raw_extraction_uses_cumulative_decoded_budget():
    raw = b"bounded data" * 100
    with pytest.raises(FormatLimit):
        qualified_zopfli_raw(zlib.compress(raw), raw, budget(decoded=len(raw)))


def test_pinned_hwp_zopfli_raw_interface_and_exact_crc_trailer():
    stronger = ole_officeart._zopfli()
    if stronger is None:
        pytest.skip("qualified optional Zopfli binding is unavailable")
    raw = b"HWP record bytes\x00\xff" * 1000
    framed = stronger(raw, numiterations=15)
    encoded = qualified_zopfli_raw(framed, raw, budget())
    assert zlib.decompress(encoded, -15) == raw
    trailer = struct.pack("<II", zlib.crc32(raw), len(raw))
    assert decode_stream(encoded + trailer, budget()) == (raw, trailer)


@pytest.mark.parametrize("size", (ZOPFLI_CUTOFF, ZOPFLI_CUTOFF + 1))
def test_hwp_optional_size_boundary_and_fixed_iteration_mapping(monkeypatch, size):
    original = weak_hwp()
    path, raw = ("DocInfo",), b"a" * size
    encoder = zlib.compressobj(0, zlib.DEFLATED, -15)
    stored = encoder.compress(raw) + encoder.flush()
    original = CompoundFile(container(original, {**original.streams, path: stored}))
    layout = HwpLayout(original, {path: raw}, 0x05000107, {path: b""})
    calls = []

    def stronger(data, numiterations):
        calls.append((len(data), numiterations))
        return zlib.compress(data, 9)

    monkeypatch.setattr(ole_officeart, "_zopfli", lambda: stronger)
    changes, details = layout.reencode(budget())
    assert calls == ([(size, 15)] if size == ZOPFLI_CUTOFF else [])
    assert details["zopfli_skipped_streams"] == (size > ZOPFLI_CUTOFF)
    assert decode_stream(changes[path], budget()) == (raw, b"")


def test_hwp_original_and_zlib_candidates_survive_larger_optional_trial(monkeypatch):
    original = weak_hwp()
    layout = inspect_hwp(original, budget())
    monkeypatch.setattr(ole_officeart, "_zopfli", lambda: None)
    baseline, report = layout.reencode(budget())
    assert "unavailable" in report["effort_note"]
    monkeypatch.setattr(
        ole_officeart, "_zopfli", lambda: lambda raw, **kwargs: zlib.compress(raw, 0)
    )
    after, report = layout.reencode(budget())
    assert after == baseline and all("zopfli" not in e for e in report["encoders"])


def test_hwp_rejects_invalid_optional_trial_without_mutating_container(monkeypatch):
    original = weak_hwp()
    before = original.data
    layout = inspect_hwp(original, budget())
    monkeypatch.setattr(ole_officeart, "_zopfli", lambda: lambda raw, **kwargs: b"invalid frame")
    with pytest.raises(ValueError):
        layout.reencode(budget())
    assert original.data == before
