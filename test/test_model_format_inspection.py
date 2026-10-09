"""Bounded inspection-only coverage for neural model containers."""

import json
import struct
from pathlib import Path

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions, inspect_distributed_checkpoint
from filerepack.__main__ import app
from filerepack.distributed_checkpoint import UnsupportedFormat
from filerepack.formats import identify_filename
from filerepack.model_formats import _external_location


def _safetensors(path: Path, tensors, payload: bytes) -> None:
    header = json.dumps(tensors, separators=(",", ":")).encode()
    header = header + b" " * (-len(header) % 8)
    path.write_bytes(struct.pack("<Q", len(header)) + header + payload)


def _gguf_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _gguf(path: Path, *, tensor_type=0, offset=0) -> None:
    header = (
        b"GGUF"
        + struct.pack("<IQQ", 3, 1, 0)
        + _gguf_string("weight")
        + struct.pack("<I", 1)
        + struct.pack("<Q", 2)
        + struct.pack("<I", tensor_type)
        + struct.pack("<Q", offset)
    )
    padding = b"\0" * (-len(header) % 32)
    path.write_bytes(header + padding + b"\0" * 8)


def _result(path: Path):
    summary = FileRepacker().repack(str(path), options=RepackOptions(quiet=True))
    assert len(summary.results) == 1
    return summary.results[0]


def test_safetensors_is_inspected_without_rewriting_payload(tmp_path, monkeypatch):
    path = tmp_path / "model.safetensors"
    payload = struct.pack("<ff", 1.0, -0.0)
    _safetensors(
        path,
        {"weight": {"dtype": "F32", "shape": [2], "data_offsets": [0, 8]}},
        payload,
    )
    original = path.read_bytes()
    monkeypatch.setattr(
        "filerepack.repack.FileSnapshot.capture",
        lambda *args, **kwargs: pytest.fail("inspection must not hash the tensor payload"),
    )

    result = _result(path)

    assert not result.replaced
    assert result.insize == result.outsize == len(original)
    assert result.details["format"] == "safetensors"
    assert result.details["tensor_count"] == 1
    assert result.details["payload_loaded"] is False
    assert result.details["writer_registered"] is False
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "tensors,payload",
    [
        ({"x": {"dtype": "F32", "shape": [2], "data_offsets": [0, 4]}}, b"1234"),
        (
            {
                "x": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]},
                "y": {"dtype": "F32", "shape": [1], "data_offsets": [2, 6]},
            },
            b"123456",
        ),
    ],
)
def test_safetensors_rejects_bad_shape_or_overlapping_ranges(tmp_path, tensors, payload):
    path = tmp_path / "bad.safetensors"
    _safetensors(path, tensors, payload)

    result = _result(path)

    assert not result.replaced
    assert "shape/dtype" in result.reason or "overlap" in result.reason


def test_gguf_header_and_tensor_ranges_are_inspected(tmp_path):
    path = tmp_path / "model.gguf"
    _gguf(path)
    original = path.read_bytes()

    result = _result(path)

    assert not result.replaced
    assert result.details["format"] == "gguf"
    assert result.details["version"] == 3
    assert result.details["tensor_count"] == 1
    assert result.details["alignment"] == 32
    assert result.details["writer_registered"] is False
    assert path.read_bytes() == original


def test_gguf_unknown_tensor_type_is_not_guessed(tmp_path):
    path = tmp_path / "unknown.gguf"
    _gguf(path, tensor_type=999)

    result = _result(path)

    assert not result.replaced
    assert "unsupported GGUF tensor type" in result.reason


def test_onnx_missing_optional_reader_is_reported_without_changes(tmp_path):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"not a protobuf model")
    original = path.read_bytes()

    result = _result(path)

    assert not result.replaced
    assert "onnx" in result.reason.lower()
    assert path.read_bytes() == original


def test_onnx_external_paths_reject_traversal_and_symlinks(tmp_path):
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"weights")
    with pytest.raises(ValueError, match="unsafe"):
        _external_location(str(tmp_path), "../outside.bin")
    with pytest.raises(ValueError, match="unsafe"):
        _external_location(str(tmp_path), "C:/outside.bin")

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "weights-link.bin").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        _external_location(str(model_dir), "weights-link.bin")


def test_onnx_checker_inspection_when_optional_dependency_is_installed(tmp_path):
    onnx = pytest.importorskip("onnx")
    helper = onnx.helper
    graph = helper.make_graph([], "empty", [], [])
    model = helper.make_model(graph, producer_name="filerepack-test")
    path = tmp_path / "model.onnx"
    onnx.save_model(model, path)

    result = _result(path)

    assert not result.replaced
    assert result.details["onnx_checker"] == "passed"
    assert result.details["graph_executed"] is False


def test_onnx_external_data_is_inventoried_without_loading_sidecar(tmp_path):
    onnx = pytest.importorskip("onnx")
    tensor = onnx.TensorProto()
    tensor.name = "weights"
    tensor.data_type = onnx.TensorProto.FLOAT
    tensor.dims.extend([2])
    tensor.data_location = onnx.TensorProto.EXTERNAL
    for key, value in (("location", "weights.bin"), ("offset", "0"), ("length", "8")):
        entry = tensor.external_data.add()
        entry.key, entry.value = key, value
    graph = onnx.helper.make_graph([], "external", [], [], initializer=[tensor])
    model = onnx.helper.make_model(graph, producer_name="filerepack-test")
    path = tmp_path / "model.onnx"
    onnx.save_model(model, path)
    (tmp_path / "weights.bin").write_bytes(b"\0" * 8)

    result = _result(path)

    assert not result.replaced
    assert result.details["external_files"] == 1
    assert result.details["external_bytes"] == 8
    assert result.details["external_data_paths"] == ["weights.bin"]
    assert result.details["onnx_checker"] == "not_run_external_data"


def test_dcp_inspection_is_opaque_and_directory_level(tmp_path):
    store = tmp_path / "checkpoint"
    store.mkdir()
    (store / ".metadata").write_bytes(b"untrusted metadata bytes")
    (store / "__0_0.distcp").write_bytes(b"shard")

    result = inspect_distributed_checkpoint(str(store))

    assert result["format"] == "pytorch-distributed-checkpoint"
    assert result["file_count"] == 2
    assert result["shard_count"] == 1
    assert result["metadata_loaded"] is False
    assert result["complete_checkpoint_verified"] is False
    assert result["writer_registered"] is False


def test_dcp_cli_and_unrouted_shard(tmp_path):
    store = tmp_path / "checkpoint"
    store.mkdir()
    (store / ".metadata").write_bytes(b"opaque")
    (store / "__0_0.distcp").write_bytes(b"bytes")
    output = CliRunner().invoke(app, ["inspect-dcp", str(store), "--json"])

    assert output.exit_code == 0
    assert json.loads(output.output)["complete_checkpoint_verified"] is False
    assert identify_filename("rank0.distcp") is None


def test_dcp_rejects_links_and_nested_layouts(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / ".metadata").write_bytes(b"opaque")
    (target / "__0_0.distcp").write_bytes(b"bytes")
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".metadata").write_bytes(b"opaque")
    (linked / "__0_0.distcp").symlink_to(target / "__0_0.distcp")
    with pytest.raises(UnsupportedFormat, match="symlink"):
        inspect_distributed_checkpoint(str(linked))

    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / ".metadata").write_bytes(b"opaque")
    (nested / "__0_0.distcp").write_bytes(b"bytes")
    (nested / "rank-1").mkdir()
    with pytest.raises(UnsupportedFormat, match="nested"):
        inspect_distributed_checkpoint(str(nested))


@pytest.mark.parametrize('options', [{'format_max_nodes': 1}, {'format_max_memory_bytes': 1}])
def test_dcp_inventory_limits_preserve_opaque_source(tmp_path, options):
    from filerepack.format_support import FormatLimit
    store = tmp_path / 'checkpoint'
    store.mkdir()
    (store / '.metadata').write_bytes(b'opaque pickle')
    (store / '__0_0.distcp').write_bytes(b'opaque shard')
    before = {path.name: path.read_bytes() for path in store.iterdir()}
    with pytest.raises(FormatLimit):
        inspect_distributed_checkpoint(str(store), options)
    assert {path.name: path.read_bytes() for path in store.iterdir()} == before
