from pathlib import Path
import pytest

from filerepack import consts
from filerepack.capabilities import capability, format_capabilities
from filerepack.dispatch import _PACKERS
from filerepack.format_registry import FORMAT_REGISTRY, STANDALONE_ALIASES
from filerepack.formats import FileKind, identify_filename, filename_exts


def test_all_routed_extensions_have_typed_records_and_adapters():
    assert len(consts.SUPPORTED_EXTS) == len(set(consts.SUPPORTED_EXTS))
    assert set(consts.SUPPORTED_EXTS) <= FORMAT_REGISTRY.keys()
    for extension in consts.SUPPORTED_EXTS:
        definition = FORMAT_REGISTRY[extension]
        kind = identify_filename('file.' + extension)
        assert kind and definition.family == kind.family
        if kind.family == 'standalone':
            assert (kind.packer or kind.key) in _PACKERS, extension
        assert extension in filename_exts('file.' + extension), extension
    for alias, canonical in STANDALONE_ALIASES.items():
        assert FORMAT_REGISTRY[alias].packer == canonical
        assert canonical in _PACKERS


def test_registry_diagnostics_do_not_advertise_unqualified_writers():
    for extension in ('safetensors', 'gguf', 'onnx'):
        item = capability(FileKind(extension, 'standalone', extension))
        assert item.inspection_only and not item.writer
    assert not capability(FileKind('cab', 'cab')).writer
    assert all(item.extension for item in format_capabilities())


def test_generated_portable_documentation_matches_registry():
    path = Path(__file__).resolve().parents[1] / 'docs/docs/formats/capabilities.md'
    if not path.exists():
        pytest.skip('Documentation is absent from this installed-artifact test environment')
    from dev.generate_capability_docs import render
    assert path.read_text() == render()
