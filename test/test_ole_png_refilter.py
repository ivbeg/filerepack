"""Independent row controls, hostile encoder results and complete PPT verification."""

import hashlib
import io
import struct
import subprocess
import zlib
from pathlib import Path

import pytest
from PIL import Image

from filerepack.format_support import Budget, FormatLimit, FormatLimits
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_officeart import encode_rasters
from filerepack.ole_raster import (
    PNG, PngIdentity, chunk, optimize_refiltered_png, png_data, qualified_png_tool,
)
from filerepack.ole_verify import CompoundFile
from test.ole_fixtures import compound_bytes
from test.ole_ppt_notes_fixtures import presentation
from test.test_ole_raster import png
from test.test_ole import native_writer as _native_writer

native_writer = _native_writer


def budget(**limits):
    return Budget(FormatLimits(**limits))


def filtered_png(color=6, filtering=4, *, mutate=False):
    width, height = 31, 13
    step = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    samples = bytes((i * 17 + i // 29) % (4 if color == 3 else 256)
                    for i in range(width * height * step))
    if mutate:
        samples = bytes([samples[0] ^ 1]) + samples[1:]
    rows, previous = [], bytes(width * step)
    for y in range(height):
        row = samples[y * width * step:(y + 1) * width * step]
        encoded = []
        for i, sample in enumerate(row):
            a = row[i - step] if i >= step else 0
            b = previous[i]
            c = previous[i - step] if i >= step else 0
            if filtering == 4:
                p = a + b - c
                distances = [(abs(p - a), 0, a), (abs(p - b), 1, b), (abs(p - c), 2, c)]
                predictor = min(distances)[2]
            else:
                predictor = (0, a, b, (a + b) // 2)[filtering]
            encoded.append((sample - predictor) & 255)
        rows.append(bytes([filtering]) + bytes(encoded))
        previous = row
    ihdr = struct.pack('>IIBBBBB', width, height, 8, color, 0, 0, 0)
    data = PNG + chunk(b'IHDR', ihdr)
    if color == 3:
        data += chunk(b'PLTE', bytes(range(12))) + chunk(b'tRNS', b'\0\x20\x40\xff')
    data += chunk(b'tEXt', b'Author\0Keep exactly')
    data += chunk(b'IDAT', zlib.compress(b''.join(rows), 0)) + chunk(b'IEND', b'')
    return data, samples


@pytest.mark.parametrize('color', [0, 2, 3, 4, 6])
@pytest.mark.parametrize('filtering', range(5))
def test_unfiltered_identity_matches_exact_samples_and_independent_decoder(color, filtering):
    data, samples = filtered_png(color, filtering)
    parsed = png_data(data, budget())
    identity = PngIdentity.from_data(parsed, refilter=True, budget=budget())
    assert identity.refilter and identity.sha256 == hashlib.sha256(samples).hexdigest()
    with Image.open(io.BytesIO(data)) as image:
        assert image.tobytes() == samples
    alternate, _ = filtered_png(color, (filtering + 1) % 5)
    second = PngIdentity.from_data(png_data(alternate, budget()), refilter=True, budget=budget())
    assert second.fingerprint() == identity.fingerprint()
    assert not identity.matches_source(png_data(alternate, budget()))


@pytest.mark.parametrize('depth,interlace', [(16, 0), (8, 1), (1, 0)])
def test_other_layouts_retain_exact_filtered_identity(depth, interlace):
    parsed = png_data(png(depth=depth, color=0, interlace=interlace), budget())
    identity = PngIdentity.from_data(parsed, refilter=True, budget=budget())
    assert not identity.refilter
    assert identity.sha256 == hashlib.sha256(parsed.raw).hexdigest()


@pytest.mark.parametrize('fault', ['sample', 'invisible-rgb', 'metadata', 'ihdr'])
def test_sample_and_metadata_changes_are_rejected_by_ppt_identity(fault):
    data, _ = filtered_png()
    original = presentation(images=[data, png()])
    first = inspect_art(original, budget())
    image = first.rasters[0].raster
    parsed = png_data(data, budget())
    raw = bytearray(parsed.raw)
    if fault in ('sample', 'invisible-rgb'):
        if fault == 'invisible-rgb':
            # A transparent control: changing hidden RGB remains a content change.
            data, _ = filtered_png(filtering=0)
            parsed = png_data(data, budget())
            raw = bytearray(parsed.raw)
            raw[4] = 0
            data = parsed.rebuild(zlib.compress(raw))
            original = presentation(images=[data, png()])
            first = inspect_art(original, budget())
            image = first.rasters[0].raster
        raw[1] ^= 1
        changed = parsed.rebuild(zlib.compress(raw))
    elif fault == 'metadata':
        changed = data.replace(chunk(b'tEXt', b'Author\0Keep exactly'),
                               chunk(b'tEXt', b'Author\0Changed'))
    else:
        ihdr = bytearray(parsed.chunks[0][1])
        ihdr[12] = 1
        changed = data.replace(chunk(b'IHDR', parsed.chunks[0][1]), chunk(b'IHDR', bytes(ihdr)))
    replacements = first.adapter.rebuild({id(first.rasters[0]): changed})
    candidate = CompoundFile(compound_bytes({**original.streams, **replacements}))
    try:
        after = inspect_art(candidate, budget())
    except ValueError:
        return
    assert not equal_art(first.identity(), after)
    assert image is not None


def fake_encoder(monkeypatch, candidate, *, result=0, error=None, version=b'oxipng 10.2.0\n'):
    from filerepack import commands

    def run(argv, **kwargs):
        if error is not None:
            raise error
        if argv[1] == '--version':
            return subprocess.CompletedProcess(argv, 0, version, b'')
        assert '--nb' in argv and '--nc' in argv and '--np' in argv
        assert argv[argv.index('--zc') + 1] == '9'
        assert '--alpha' not in argv and '--strip' not in argv
        Path(argv[argv.index('--out') + 1]).write_bytes(candidate)
        return subprocess.CompletedProcess(argv, result, b'', b'')

    monkeypatch.setattr(commands, '_cancelable_run', run)


@pytest.mark.parametrize('fault', ['sample', 'ihdr', 'crc', 'exit', 'launch'])
def test_bad_optional_encoder_retains_verified_original_filter_alternatives(monkeypatch, fault):
    data, _ = filtered_png()
    parsed = png_data(data, budget())
    trial, _ = filtered_png(filtering=0, mutate=fault == 'sample')
    trial = png_data(trial, budget()).rebuild(zlib.compress(png_data(trial, budget()).raw, 9))
    if fault == 'ihdr':
        trial = png(color=2)
    elif fault == 'crc':
        trial = trial[:-1] + bytes([trial[-1] ^ 1])
    fake_encoder(monkeypatch, trial, result=int(fault == 'exit'),
                 error=OSError('missing tool') if fault == 'launch' else None)
    skips = []
    result, encoder = optimize_refiltered_png(
        data, parsed, PngIdentity.from_data(parsed, refilter=True), budget(),
        tool='qualified-test-tool', skips=skips,
    )
    assert not encoder.startswith('png-oxipng') and skips
    assert png_data(result, budget()).fingerprint() == parsed.fingerprint()


def test_optional_encoder_metadata_is_restored_exactly(monkeypatch):
    data, _ = filtered_png()
    parsed = png_data(data, budget())
    trial, _ = filtered_png(filtering=0)
    trial = trial.replace(chunk(b'tEXt', b'Author\0Keep exactly'), b'')
    trial = png_data(trial, budget()).rebuild(zlib.compress(png_data(trial, budget()).raw, 9))
    fake_encoder(monkeypatch, trial)
    from filerepack.ole_raster import _png_refilter_trial

    result = _png_refilter_trial(
        data, parsed, PngIdentity.from_data(parsed, refilter=True), 'test-tool', budget()
    )
    after = png_data(result, budget())
    assert [c for c in after.chunks if c[0] != b'IDAT'] == \
        [c for c in parsed.chunks if c[0] != b'IDAT']
    assert PngIdentity.from_data(after, refilter=True).fingerprint() == \
        PngIdentity.from_data(parsed, refilter=True).fingerprint()


def test_missing_and_unqualified_optional_tools_keep_png_compression(monkeypatch):
    from filerepack import tools

    monkeypatch.setattr(tools, 'resolve_tool', lambda key: None)
    layout = inspect_art(presentation(), budget())
    skips = []
    replacements, _ = encode_rasters(layout.rasters, budget(), skips=skips)
    assert replacements and 'unavailable' in skips[0]
    monkeypatch.setattr(tools, 'resolve_tool', lambda key: 'tool')
    fake_encoder(monkeypatch, b'', version=b'oxipng 0.0.0\n')
    tool, reason = qualified_png_tool(budget())
    assert tool is None and 'requires qualified' in reason


def test_encoder_budget_exhaustion_is_not_a_fallback(monkeypatch):
    data, _ = filtered_png()
    parsed = png_data(data, budget())
    fake_encoder(monkeypatch, b'', error=FormatLimit('root exhausted'))
    with pytest.raises(FormatLimit, match='root exhausted'):
        optimize_refiltered_png(data, parsed, PngIdentity.from_data(parsed, refilter=True),
                         budget(), tool='test-tool')


def test_local_encoder_trial_ceiling_keeps_verified_choices(monkeypatch):
    data, _ = filtered_png()
    parsed = png_data(data, budget())
    fake_encoder(monkeypatch, b'', error=subprocess.TimeoutExpired('test-tool', 1))
    skips = []
    result, encoder = optimize_refiltered_png(
        data, parsed, PngIdentity.from_data(parsed, refilter=True), budget(),
        tool='test-tool', skips=skips,
    )
    assert encoder == 'png-zlib9' and len(result) < len(data)
    assert png_data(result, budget()).fingerprint() == parsed.fingerprint()
    assert any('trial time limit reached' in reason for reason in skips)


def test_encoder_reserves_final_verification_time(monkeypatch):
    data, _ = filtered_png()
    parsed = png_data(data, budget())

    def unexpected_trial(*args, **kwargs):
        pytest.fail('The final verification time must be reserved')

    monkeypatch.setattr('filerepack.commands._cancelable_run', unexpected_trial)
    skips = []
    result, encoder = optimize_refiltered_png(
        data, parsed, PngIdentity.from_data(parsed, refilter=True), budget(seconds=20),
        tool='test-tool', skips=skips,
    )
    assert encoder == 'png-zlib9' and len(result) < len(data)
    assert any('time allowance exhausted' in reason for reason in skips)


def test_larger_optional_candidate_cannot_displace_smallest_verified_result(monkeypatch):
    data, _ = filtered_png()
    parsed = png_data(data, budget())
    fake_encoder(monkeypatch, data + b'larger')
    result, encoder = optimize_refiltered_png(
        data, parsed, PngIdentity.from_data(parsed, refilter=True), budget(), tool='test-tool'
    )
    assert encoder == 'png-zlib9' and len(result) < len(data)


def test_filter_work_checks_deadline_between_rows():
    data, _ = filtered_png()
    parsed = png_data(data, budget())
    with pytest.raises(FormatLimit):
        PngIdentity.from_data(parsed, refilter=True, budget=budget(seconds=0))


@pytest.mark.parametrize('color', [0, 2, 3, 4, 6])
@pytest.mark.parametrize('filtering', range(5))
def test_native_row_decoder_matches_python_and_independent_samples(native_writer, color, filtering):
    from filerepack.format_support import format_scope

    capabilities = subprocess.check_output([native_writer, '--capabilities']).split()
    if b'png-unfilter-v1' not in capabilities:
        pytest.skip('Rebuild optional OLE helper for png-unfilter-v1')
    data, samples = filtered_png(color, filtering)
    parsed = png_data(data, budget())
    reference = PngIdentity.from_data(parsed, refilter=True)
    with format_scope({'ole_writer': native_writer}) as root:
        identity = PngIdentity.from_data(parsed, refilter=True, budget=root)
        assert identity.fingerprint() == reference.fingerprint()
        assert identity.sha256 == hashlib.sha256(samples).hexdigest()
        assert root.written == len(parsed.raw) + len(samples)


@pytest.mark.parametrize('fault', ['filter', 'trailing', 'truncated', 'palette'])
def test_native_row_decoder_rejects_invalid_filtered_bytes(native_writer, fault):
    from filerepack.format_support import format_scope
    from filerepack.ole_raster import PngData, _native_png_samples_digest

    if b'png-unfilter-v1' not in subprocess.check_output([native_writer, '--capabilities']).split():
        pytest.skip('Rebuild optional OLE helper for png-unfilter-v1')
    data, _ = filtered_png(color=3 if fault == 'palette' else 6, filtering=0)
    parsed = png_data(data, budget())
    raw = bytearray(parsed.raw)
    if fault == 'filter':
        raw[0] = 5
    elif fault == 'palette':
        raw[1] = 4
    elif fault == 'trailing':
        raw.append(0)
    else:
        raw.pop()
    with format_scope({'ole_writer': native_writer}) as root:
        with pytest.raises(ValueError, match='native PNG row verification failed'):
            _native_png_samples_digest(PngData(parsed.chunks, bytes(raw)), native_writer, root)


def test_old_native_helper_retains_python_checks_and_probes_once(monkeypatch):
    from filerepack import commands
    from filerepack.format_support import format_scope

    calls = []

    def old_helper(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, b'compact-v3\n', b'')

    monkeypatch.setattr(commands, '_cancelable_run', old_helper)
    data, samples = filtered_png()
    parsed = png_data(data, budget())
    with format_scope({'ole_writer': 'old-helper'}) as root:
        for _ in range(2):
            assert PngIdentity.from_data(parsed, refilter=True, budget=root).sha256 == \
                hashlib.sha256(samples).hexdigest()
        assert root.written == 0
    assert calls == [['old-helper', '--capabilities']]
