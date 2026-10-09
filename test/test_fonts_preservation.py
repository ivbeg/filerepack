import struct
import zlib

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.fonts import fingerprint
from filerepack.format_support import Budget, FormatLimits
from filerepack.verification import verify_preservation


def font(path, flavor):
    pytest.importorskip('fontTools')
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.sfnt import WOFFFlavorData
    from fontTools.ttLib.woff2 import WOFF2FlavorData
    builder = FontBuilder(1000, isTTF=True)
    glyphs = ['.notdef', 'A']
    builder.setupGlyphOrder(glyphs)
    builder.setupCharacterMap({65: 'A'})
    builder.setupGlyf({name: TTGlyphPen(None).glyph() for name in glyphs})
    builder.setupHorizontalMetrics({name: (600, 0) for name in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': 'Preserved', 'styleName': 'Regular'})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    builder.font['head'].created = builder.font['head'].modified = 1234567890
    builder.font.recalcTimestamp = False
    builder.font.flavor = flavor
    metadata = b'<metadata version="1.0"><description>' + b'keep all licenses. ' * 5000
    metadata += b'</description></metadata>'
    data = WOFFFlavorData() if flavor == 'woff' else WOFF2FlavorData()
    data.metaData, data.privData = metadata, b'private data\0\xff'
    data.majorVersion, data.minorVersion = 7, 3
    builder.font.flavorData = data
    builder.save(path)
    original = path.read_bytes()
    offset = 24 if flavor == 'woff' else 28
    meta_at, _, _ = struct.unpack_from('>III', original, offset)
    if flavor == 'woff':
        compressed = zlib.compress(metadata, 1)
    else:
        brotli = pytest.importorskip('brotli')
        compressed = brotli.compress(metadata, quality=1)
    rebuilt = bytearray(original[:meta_at] + compressed)
    rebuilt.extend(b'\0' * (-len(rebuilt) % 4))
    private_at = len(rebuilt)
    rebuilt.extend(data.privData)
    struct.pack_into('>I', rebuilt, 8, len(rebuilt))
    struct.pack_into('>III', rebuilt, offset, meta_at, len(compressed), len(metadata))
    struct.pack_into('>II', rebuilt, 40 if flavor == 'woff2' else 36,
                     private_at, len(data.privData))
    path.write_bytes(rebuilt)


@pytest.mark.parametrize('flavor', ['woff', 'woff2'])
def test_font_tables_timestamp_optional_metadata_and_private_data(tmp_path, flavor):
    source, target = tmp_path / ('source.' + flavor), tmp_path / ('out.' + flavor)
    font(source, flavor)
    original = source.read_bytes()
    before = fingerprint(str(source), Budget(FormatLimits()))
    result = FileRepacker().repack(str(source), outfile=str(target))
    assert result.outcome.status == 'replaced', result.outcome.reason
    assert fingerprint(str(target), Budget(FormatLimits())) == before
    assert source.read_bytes() == original
    assert verify_preservation(str(source), str(target), flavor)


@pytest.mark.parametrize('flavor', ['woff', 'woff2'])
def test_font_changed_metadata_rejected(tmp_path, flavor):
    pytest.importorskip('fontTools')
    from fontTools.ttLib import TTFont
    source, target = tmp_path / ('source.' + flavor), tmp_path / ('changed.' + flavor)
    font(source, flavor)
    with TTFont(source, recalcTimestamp=False) as candidate:
        candidate.flavorData.privData = b'changed private data'
        candidate.save(target)
    assert not verify_preservation(str(source), str(target), flavor)
    original = source.read_bytes()
    result = FileRepacker().repack(str(source), options=RepackOptions(format_max_memory_bytes=1))
    assert result.outcome.status == 'skipped' and source.read_bytes() == original
