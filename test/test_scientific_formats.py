"""Native-reader and adversarial gates for the evidence-based preserving profiles."""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import threading
import zipfile
from pathlib import Path

import pytest

from filerepack import FileRepacker, RepackOptions, repack_store
from filerepack.format_support import FormatLimit, format_scope, run_operation
from filerepack.formats import identify_filename
from filerepack.validation import validate_options

pytest.importorskip("psutil")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rewrite(kind, source, **options):
    candidate = source.with_name(source.name + ".candidate")
    info = run_operation(kind, "rewrite", str(source), str(candidate), options)
    return candidate, info


@pytest.mark.parametrize("version", [2, 3])
@pytest.mark.parametrize("workspace", [False, True])
@pytest.mark.parametrize("codec", ["FALSE", '"gzip"', '"bzip2"', '"xz"'])
def test_r_native_roundtrip(tmp_path, version, workspace, codec):
    r = shutil.which("Rscript")
    if not r:
        pytest.skip("native R reader missing")
    source = tmp_path / ("data.RData" if workspace else "data.RDS")
    value = (
        "shared <- new.env(); shared$value <- 1L; "
        "x <- list(i=rep(1:100,100),l=c(TRUE,NA,FALSE),r=as.raw(0:255),"
        'f=c(0,-0,NaN,NA_real_,Inf),u="кириллица", ref=list(shared,shared)); '
        'attr(x,"label") <- "test"; '
    )
    command = (
        f'save(x,file="{source}",compress={codec},version={version})'
        if workspace
        else (f'saveRDS(x,file="{source}",compress={codec},version={version})')
    )
    subprocess.run([r, "-e", value + command], check=True, capture_output=True)
    before = digest(source)
    candidate, info = rewrite("r-serialization", source, r_compression="xz")
    assert info["changed"]
    if workspace:
        check = (
            f'a<-new.env();b<-new.env();load("{source}",a);load("{candidate}",b);'
            "stopifnot(identical(a$x$i,b$x$i),identical(a$x$f,b$x$f),"
            "identical(b$x$ref[[1]],b$x$ref[[2]]))"
        )
    else:
        check = (
            f'a<-readRDS("{source}");b<-readRDS("{candidate}");'
            "stopifnot(identical(a$i,b$i),identical(a$f,b$f),"
            "identical(attributes(a),attributes(b)),identical(b$ref[[1]],b$ref[[2]]))"
        )
    subprocess.run([r, "-e", check], check=True, capture_output=True)
    assert digest(source) == before
    assert run_operation("r-serialization", "compare", str(source), str(candidate))["equal"]


def test_r_bad_envelope_and_unexecutable_records(tmp_path):
    import gzip

    # A syntactically valid header with an external-pointer object is outside the profile.
    raw = b"X\n" + struct.pack(">4i", 2, 0x40300, 0x20300, 22)
    path = tmp_path / "x.rds"
    path.write_bytes(gzip.compress(raw))
    with pytest.raises(ValueError, match="unsupported"):
        rewrite("r-serialization", path)
    path.write_bytes(path.read_bytes() + b"trailing")
    with pytest.raises(ValueError, match="trailing"):
        rewrite("r-serialization", path)


def test_mat_existing_envelope_secondary_reader(tmp_path):
    scipy = pytest.importorskip("scipy.io")
    np = pytest.importorskip("numpy")
    source = tmp_path / "x.mat"
    values = {"x": np.zeros((100, 100)), "c": np.arange(10) + 1j, "u": "hello"}
    scipy.savemat(source, values, do_compression=True)
    before = digest(source)
    candidate, info = rewrite("mat", source, experimental_formats=True)
    assert info["details"]["experimental"]
    other = scipy.loadmat(candidate)
    for name in ("x", "c"):
        assert np.array_equal(other[name], scipy.loadmat(source)[name])
    assert digest(source) == before
    result = FileRepacker().repack_zip_file(str(source))
    assert not result.results[0].replaced
    assert "MATLAB" in result.results[0].reason


@pytest.mark.parametrize("corruption", ["checksum", "length", "subsystem"])
def test_mat_invalid_framing(tmp_path, corruption):
    scipy = pytest.importorskip("scipy.io")
    np = pytest.importorskip("numpy")
    source = tmp_path / "x.mat"
    scipy.savemat(source, {"x": np.zeros((20, 20))}, do_compression=True)
    data = bytearray(source.read_bytes())
    if corruption == "checksum":
        data[-1] ^= 1
    elif corruption == "subsystem":
        data[116] = 1
    else:
        data[132:136] = struct.pack("<I", len(data))
    source.write_bytes(data)
    with pytest.raises(ValueError):
        rewrite("mat", source, experimental_formats=True)


def test_hdf_graph_and_native_values(tmp_path):
    h5py = pytest.importorskip("h5py")
    np = pytest.importorskip("numpy")
    if not shutil.which("h5repack"):
        pytest.skip("h5repack missing")
    source = tmp_path / "graph.h5"
    with h5py.File(source, "w", userblock_size=512) as f:
        x = f.create_dataset(
            "x", data=np.zeros((1000,)), compression="gzip", compression_opts=1, chunks=(100,)
        )
        x.attrs["label"] = "hello"
        f["alias"] = x
        group = f.create_group("group")
        group["cycle"] = f["/"]
        f["soft"] = h5py.SoftLink("/x")
        f["external"] = h5py.ExternalLink("absent.h5", "/not-followed")
        f.create_dataset("references", data=[x.ref], dtype=h5py.ref_dtype)
        f.create_dataset("regions", data=[x.regionref[1:5]], dtype=h5py.regionref_dtype)
    with source.open("r+b") as f:
        f.write(b"kept user block")
    candidate, info = rewrite("hdf5-native", source)
    assert info["equal"]
    assert candidate.read_bytes()[:512] == source.read_bytes()[:512]
    with h5py.File(candidate) as f:
        assert f["alias"].id == f["x"].id
        assert f[f["references"][0]].id == f["x"].id
        assert f["x"][f["regions"][0]].shape == (4,)
        assert isinstance(f.get("external", getlink=True), h5py.ExternalLink)
        assert np.array_equal(f["x"][:], np.zeros(1000))


@pytest.mark.parametrize("model", ["NETCDF4", "NETCDF4_CLASSIC"])
def test_netcdf_model_raw_packing_and_unlimited(tmp_path, model):
    netcdf = pytest.importorskip("netCDF4")
    np = pytest.importorskip("numpy")
    source = tmp_path / "packed.nc"
    with netcdf.Dataset(source, "w", format=model) as f:
        f.createDimension("time", None)
        x = f.createVariable(
            "x", "i2", ("time",), zlib=True, complevel=1, chunksizes=(100,), fill_value=-32767
        )
        x.set_auto_maskandscale(False)
        x.scale_factor = 0.1
        x.add_offset = 20.0
        x[:] = np.array([0, 1, -32767] * 1000, dtype="i2")
        if model == "NETCDF4":
            f.createGroup("metadata").description = "preserve"
    candidate, info = rewrite("netcdf-native", source)
    assert info["equal"]
    with netcdf.Dataset(source) as a, netcdf.Dataset(candidate) as b:
        a.set_auto_maskandscale(False)
        b.set_auto_maskandscale(False)
        assert a.data_model == b.data_model == model
        assert np.array_equal(a["x"][:], b["x"][:])
        assert b.dimensions["time"].isunlimited()
        assert a["x"].chunking() == b["x"].chunking()


@pytest.mark.parametrize("model", ["NETCDF3_CLASSIC", "NETCDF3_64BIT_OFFSET", "NETCDF3_64BIT_DATA"])
def test_classic_netcdf_retained(tmp_path, model):
    netcdf = pytest.importorskip("netCDF4")
    source = tmp_path / "x.nc"
    with netcdf.Dataset(source, "w", format=model) as f:
        f.createDimension("x", 10)
        f.createVariable("x", "i4", ("x",))[:] = 0
    original = digest(source)
    outcome = FileRepacker().repack_zip_file(str(source))
    assert not outcome.results[0].replaced
    assert "conversion" in outcome.results[0].reason
    assert digest(source) == original


@pytest.mark.parametrize("big,endian", [(False, "<"), (False, ">"), (True, "<")])
@pytest.mark.parametrize("dtype", ["uint16", "int32", "float64"])
def test_tiff_native_tags_samples_and_geometry(tmp_path, big, endian, dtype):
    tifffile = pytest.importorskip("tifffile")
    np = pytest.importorskip("numpy")
    pytest.importorskip("imagecodecs")
    source = tmp_path / "x.tif"
    data = np.zeros((80, 80), dtype=dtype)
    tifffile.imwrite(
        source,
        data,
        bigtiff=big,
        byteorder=endian,
        metadata=None,
        rowsperstrip=8,
        description="retain exact description",
        extratags=[(700, "B", 4, b"xmp!", False)],
    )
    candidate, info = rewrite("tiff-native", source)
    assert info["equal"]
    assert np.array_equal(tifffile.imread(candidate), data)
    with tifffile.TiffFile(source) as a, tifffile.TiffFile(candidate) as b:
        assert a.pages[0].tags[700].value == b.pages[0].tags[700].value
        assert a.pages[0].description == b.pages[0].description
        assert a.pages[0].rowsperstrip == b.pages[0].rowsperstrip


def test_tiff_subifds_and_unknown_private_tags(tmp_path):
    tifffile = pytest.importorskip("tifffile")
    np = pytest.importorskip("numpy")
    source = tmp_path / "pyramid.tif"
    with tifffile.TiffWriter(source) as writer:
        writer.write(np.zeros((32, 32), dtype="uint8"), subifds=1, metadata=None)
        writer.write(np.zeros((16, 16), dtype="uint8"), subfiletype=1, metadata=None)
    candidate, info = rewrite("tiff-native", source)
    assert info["equal"]
    with tifffile.TiffFile(candidate) as f:
        assert len(f.pages[0].pages) == 1
    tifffile.imwrite(
        source, np.zeros((10, 10), dtype="uint8"), extratags=[(55000, "I", 1, 123, False)]
    )
    with pytest.raises(ValueError, match="unknown"):
        rewrite("tiff-native", source)


@pytest.fixture
def checkpoint(tmp_path):
    torch = pytest.importorskip("torch")
    source = tmp_path / "state.pt"
    base = torch.zeros(5000, dtype=torch.float32)
    # Large metadata gives useful default-profile gain with unchanged tensor storage.
    torch.save({**{f"parameter_{i:05}": base for i in range(1500)}, "view": base[3::2]}, source)
    return source


@pytest.mark.parametrize("policy", ["preserve-mmap", "load-only"])
def test_checkpoint_native_tensor_views_and_mmap(checkpoint, policy):
    import torch

    before = digest(checkpoint)
    candidate, info = rewrite("checkpoint", checkpoint, checkpoint_compatibility=policy)
    assert info["equal"] and candidate.stat().st_size < checkpoint.stat().st_size
    a = torch.load(checkpoint, weights_only=True, mmap=True)
    b = torch.load(candidate, weights_only=True, mmap=policy == "preserve-mmap")
    for name in a:
        assert torch.equal(
            a[name].contiguous().view(torch.uint8), b[name].contiguous().view(torch.uint8)
        )
        assert a[name].stride() == b[name].stride()
        assert a[name].storage_offset() == b[name].storage_offset()
    assert (
        b["view"].untyped_storage().data_ptr() == b["parameter_00000"].untyped_storage().data_ptr()
    )
    assert digest(checkpoint) == before
    if policy == "load-only":
        with pytest.raises(RuntimeError):
            torch.load(candidate, weights_only=True, mmap=True)


def test_checkpoint_renamed_and_unknown_layout_protection(checkpoint, tmp_path):
    renamed = tmp_path / "model.zip"
    shutil.copyfile(checkpoint, renamed)
    assert identify_filename(str(renamed), peek_path=str(renamed)).packer == "checkpoint"
    with zipfile.ZipFile(renamed, "a") as f:
        f.writestr("state/code/__torch__.py", "unrecognized TorchScript layout")
    before = digest(renamed)
    result = FileRepacker().repack_zip_file(str(renamed))
    assert "unknown" in result.results[0].reason
    assert digest(renamed) == before


def test_checkpoint_malicious_pickle_never_loaded(checkpoint, tmp_path):
    marker = tmp_path / "execution-marker"
    # This pickle would execute touch if unpickled; production only compares member bytes.
    payload = b'cos\nsystem\n(S"touch ' + str(marker).encode() + b'"\ntR.'
    source = tmp_path / "payload.pt"
    with zipfile.ZipFile(checkpoint) as original, zipfile.ZipFile(source, "w") as target:
        for info in original.infolist():
            target.writestr(
                info, payload if info.filename.endswith("/data.pkl") else original.read(info)
            )
    candidate, info = rewrite("checkpoint", source, checkpoint_compatibility="load-only")
    assert info["equal"] and candidate.exists() and not marker.exists()


@pytest.mark.parametrize("mode", ["raw", "bytecode", "zlib"])
def test_spss_dictionary_native_reader_and_exact_float_bits(tmp_path, mode):
    readstat = pytest.importorskip("pyreadstat")
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    source = tmp_path / ("x.zsav" if mode == "zlib" else "x.sav")
    frame = pd.DataFrame(
        {"num": [0.0, -0.0, 1.0, np.nan] * 500, "text": ["a", "        ", "long-ish", "z"] * 500}
    )
    readstat.write_sav(
        frame,
        str(source),
        compress=mode == "zlib",
        row_compress=mode == "bytecode",
        column_labels={"num": "number"},
        variable_value_labels={"num": {1: "one"}},
        missing_ranges={"num": [{"lo": 98, "hi": 99}]},
    )
    if mode == "zlib":
        inspection = run_operation("spss", "inspect", str(source))
        assert inspection["details"]["experimental"] is True
        refused_path = tmp_path / "refused.zsav"
        refused = run_operation("spss", "rewrite", str(source), str(refused_path))
        assert not refused["changed"] and not refused_path.exists()
        assert refused["details"]["experimental"] is True
    candidate, info = rewrite("spss", source, experimental_formats=True)
    assert info["equal"]
    a, am = readstat.read_sav(str(source), user_missing=True)
    b, bm = readstat.read_sav(str(candidate), user_missing=True)
    assert a.equals(b)
    for field in ("column_names", "column_labels", "variable_value_labels", "missing_ranges"):
        assert getattr(am, field) == getattr(bm, field)


@pytest.fixture
def store(tmp_path):
    zarr = pytest.importorskip("zarr")
    np = pytest.importorskip("numpy")
    numcodecs = pytest.importorskip("numcodecs")
    root = tmp_path / "data.zarr"
    group = zarr.open_group(str(root), mode="w")
    array = group.create_dataset(
        "data",
        shape=(301,),
        chunks=(100,),
        dtype=">f8",
        order="F",
        compressor=numcodecs.Blosc(cname="lz4", clevel=1),
    )
    array[:] = np.zeros(301)
    group.attrs["description"] = "retained"
    (root / "notes.txt").write_text("keep auxiliary bytes")
    zarr.consolidate_metadata(str(root))
    return root


def test_zarr_complete_native_consolidated_store(store, tmp_path):
    import zarr
    import numpy as np

    before = {str(p.relative_to(store)): digest(p) for p in store.rglob("*") if p.is_file()}
    result = repack_store(str(store), str(tmp_path / "output"))
    assert result.replaced
    a = zarr.open(str(store), mode="r")
    b = zarr.open_consolidated(result.destination, mode="r")
    assert np.array_equal(a["data"][:], b["data"][:])
    assert dict(a.attrs) == dict(b.attrs)
    assert (Path(result.destination) / "notes.txt").read_bytes() == (
        store / "notes.txt"
    ).read_bytes()
    assert before == {str(p.relative_to(store)): digest(p) for p in store.rglob("*") if p.is_file()}
    assert not list((tmp_path / "output").glob(".filerepack-store-*"))


@pytest.mark.parametrize("fault", ["stale", "corrupt", "symlink", "collision", "object"])
def test_zarr_refuses_unproven_trees(store, tmp_path, fault):
    if fault == "stale":
        (store / ".zattrs").write_text('{"changed": true}')
    elif fault == "corrupt":
        (store / "data/0").write_bytes(b"bad compressed data")
    elif fault == "symlink":
        (store / "link").symlink_to(store / "notes.txt")
    elif fault == "collision":
        (store / "Notes.txt").write_text("different")
        if os.path.samefile(store / "Notes.txt", store / "notes.txt"):
            pytest.skip("source filesystem cannot represent case-colliding keys")
    else:
        path = store / "data/.zarray"
        metadata = json.loads(path.read_text())
        metadata["dtype"] = "|O"
        path.write_text(json.dumps(metadata))
        (store / ".zmetadata").unlink()
    output = tmp_path / "output"
    with pytest.raises(ValueError):
        repack_store(str(store), str(output))
    assert not (output / store.name).exists()
    assert not list(output.glob(".filerepack-store-*"))


def test_zarr_disjointness_existing_and_publication_race(store, tmp_path, monkeypatch):
    from filerepack import zarr_store

    with pytest.raises(ValueError, match="disjoint"):
        repack_store(str(store), str(store / "inside"))
    output = tmp_path / "output"
    output.mkdir()
    final = output / store.name
    final.mkdir()
    (final / "kept").write_text("existing")
    with pytest.raises(FileExistsError):
        repack_store(str(store), str(output))
    shutil.rmtree(final)
    original = zarr_store.publish_directory

    def race(source, destination):
        if destination == str(final):
            final.mkdir()
            (final / "race").write_text("winner")
        original(source, destination)

    monkeypatch.setattr(zarr_store, "publish_directory", race)
    with pytest.raises(FileExistsError):
        repack_store(str(store), str(output))
    assert (final / "race").read_text() == "winner"
    assert not list(output.glob(".filerepack-store-*"))


def test_zarr_source_generation_changed(store, tmp_path, monkeypatch):
    from filerepack import zarr_store

    original = zarr_store.run_operation

    def changed(kind, action, *args, **kwargs):
        result = original(kind, action, *args, **kwargs)
        if action == "rewrite":
            (store / "notes.txt").write_text("concurrent change")
        return result

    monkeypatch.setattr(zarr_store, "run_operation", changed)
    with pytest.raises(ValueError, match="changed"):
        repack_store(str(store), str(tmp_path / "output"))
    assert not (tmp_path / "output" / store.name).exists()


def test_dryrun_scientific_allocates_no_candidate_or_workspace(store, tmp_path, monkeypatch):
    from filerepack import candidates, repack

    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run allocated a candidate/workspace")

    monkeypatch.setattr(candidates, "make_temp", forbidden)
    monkeypatch.setattr(repack.tempfile, "TemporaryDirectory", forbidden)
    source = tmp_path / "data.rds"
    import gzip

    source.write_bytes(gzip.compress(b"X\n" + struct.pack(">4i", 2, 0x40300, 0x20300, 254)))
    result = FileRepacker().repack_zip_file(str(source), def_options=RepackOptions(dryrun=True))
    assert "inspected" in result.results[0].reason
    output = tmp_path / "absent"
    outcome = repack_store(str(store), str(output), {"dryrun": True})
    assert not outcome.replaced and not output.exists()


@pytest.mark.parametrize(
    "limit,value",
    [
        ("format_max_decoded_bytes", 1),
        ("format_max_memory_bytes", 1024),
        ("format_max_scratch_bytes", 1),
        ("format_max_nodes", 1),
        ("format_timeout", 0.001),
    ],
)
def test_isolation_budgets_preserve_source(tmp_path, limit, value):
    import gzip

    source = tmp_path / "x.rds"
    source.write_bytes(gzip.compress(b"X\n" + struct.pack(">4i", 2, 0x40300, 0x20300, 254)))
    before = digest(source)
    result = FileRepacker().repack_zip_file(str(source), def_options={limit: value})
    assert not result.results[0].replaced
    assert digest(source) == before
    assert "budget" in result.results[0].reason or "bounded" in result.results[0].reason


def test_staging_budget_refusal_reports_existing_source(tmp_path, monkeypatch):
    import gzip
    from filerepack import repack

    def forbidden(*args, **kwargs):
        raise AssertionError("staging allocated after its copy budget was exhausted")

    source = tmp_path / "x.rds"
    source.write_bytes(gzip.compress(b"X\n" + struct.pack(">4i", 2, 0x40300, 0x20300, 254)))
    before = digest(source)
    destination = tmp_path / "absent.rds"
    monkeypatch.setattr(repack.tempfile, "TemporaryDirectory", forbidden)
    result = FileRepacker().repack_zip_file(
        str(source), outfile=str(destination), def_options={"format_max_scratch_bytes": 1}
    )
    assert result.filepath == str(source)
    assert result.results[0].filepath == str(source)
    assert not result.results[0].replaced and not destination.exists()
    assert digest(source) == before


@pytest.mark.parametrize("outcome", ["budget", "unsupported", "no-benefit"])
def test_scientific_refusal_preserves_prior_destination(tmp_path, outcome):
    source = tmp_path / "x.rds"
    source.write_bytes(
        b"unsupported" if outcome == "unsupported"
        else b"X\n" + struct.pack(">4i", 2, 0x40300, 0x20300, 254)
    )
    destination = tmp_path / "previous.rds"
    destination.write_bytes(b"prior destination")
    original, prior = digest(source), digest(destination)
    options = {
        "overwrite": True,
        "format_max_memory_bytes": 1024 if outcome == "budget" else 256 * 1024**2,
    }
    result = FileRepacker().repack_zip_file(
        str(source), outfile=str(destination), def_options=options
    )
    assert digest(source) == original and digest(destination) == prior
    assert result.filepath == result.results[0].filepath == str(source)
    assert not result.results[0].replaced


def test_isolation_cancellation_and_cumulative_budget(tmp_path):
    event = threading.Event()
    event.set()
    source = tmp_path / "x"
    source.write_bytes(b"not needed")
    with pytest.raises(FormatLimit, match="cancelled"):
        run_operation("r-serialization", "inspect", str(source), options={"_cancel_event": event})
    with format_scope({"format_max_nodes": 2}) as budget:
        budget.consume(nodes=1)
        with format_scope({"format_max_nodes": 999}) as same:
            assert budget is same
            with pytest.raises(FormatLimit):
                same.consume(nodes=2)


@pytest.mark.parametrize("failure", ["memory", "exit", "control"])
def test_interrupted_worker_keeps_root_accounting_closed(tmp_path, monkeypatch, failure):
    from filerepack import format_support
    from filerepack.format_support import UnsupportedFormat

    source = tmp_path / "x.rds"
    source.write_bytes(b"X\n" + struct.pack(">4i", 2, 0x40300, 0x20300, 254))
    options = {"format_max_memory_bytes": 1024} if failure == "memory" else {}
    if failure != "memory":
        original_popen = format_support.subprocess.Popen
        command = "import sys; sys.stdin.read(); "
        command += "sys.exit(3)" if failure == "exit" else "print('invalid JSON')"

        def failed_worker(*args, **kwargs):
            return original_popen([format_support.sys.executable, "-c", command], **kwargs)

        monkeypatch.setattr(format_support.subprocess, "Popen", failed_worker)
    error = FormatLimit if failure == "memory" else UnsupportedFormat
    reason = {"memory": "worker memory", "exit": "worker failed", "control": "control output"}
    with format_scope(options):
        with pytest.raises(error, match=reason[failure]):
            run_operation("r-serialization", "inspect", str(source))

        def forbidden(*args, **kwargs):
            raise AssertionError("new worker started without accounting for the terminated worker")

        monkeypatch.setattr(format_support.subprocess, "Popen", forbidden)
        with pytest.raises(FormatLimit, match="accounting incomplete"):
            run_operation("r-serialization", "inspect", str(source))


@pytest.mark.parametrize(
    "option,value",
    [
        ("r_compression", "zstd"),
        ("checkpoint_compatibility", "lossy"),
        ("zarr_codec_policy", "pickle"),
        ("format_max_memory_bytes", 0),
        ("experimental_formats", "yes"),
    ],
)
def test_invalid_options_rejected(option, value):
    with pytest.raises(ValueError):
        validate_options({option: value})


def test_cli_and_bulk_carry_compatibility_options(checkpoint, tmp_path):
    from typer.testing import CliRunner
    from filerepack.__main__ import app
    from filerepack.jobs import process_file_job

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "repack",
            str(checkpoint),
            "--checkpoint-compatibility",
            "load-only",
            "--dryrun",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert output["files"][0]["details"]["mmap"] is False
    result = process_file_job(
        {"filepath": str(checkpoint), "checkpoint_compatibility": "load-only", "dryrun": True}
    )
    assert result["status"] == "predicted"
    invalid = runner.invoke(app, ["repack", str(checkpoint), "--r-compression", "zstd"])
    assert invalid.exit_code != 0


def test_zarr_no_benefit_and_codec_upgrade(store, tmp_path):
    outcome = repack_store(str(store), str(tmp_path / "rejected"), {"min_savings": 100})
    assert not outcome.replaced
    assert not Path(outcome.destination).exists()
    assert not list((tmp_path / "rejected").glob(".filerepack-store-*"))
    result = repack_store(
        str(store), str(tmp_path / "upgraded"), {"zarr_codec_policy": "compatible-upgrade"}
    )
    assert result.replaced
    import zarr

    assert zarr.open(result.destination, mode="r")["data"].compressor.cname == "zstd"


def test_netcdf_geometry_changed_rejected(tmp_path):
    nc = pytest.importorskip("netCDF4")
    source, candidate = tmp_path / "x.nc", tmp_path / "different.nc"
    for path, geometry in [(source, (50,)), (candidate, (100,))]:
        with nc.Dataset(path, "w") as f:
            f.createDimension("x", 100)
            f.createVariable("x", "i4", ("x",), zlib=True, chunksizes=geometry)[:] = 0
    with pytest.raises(ValueError, match="changed"):
        run_operation("netcdf-native", "compare", str(source), str(candidate))


def test_spss_damaged_dictionary_and_zlib_offsets(tmp_path):
    readstat = pytest.importorskip("pyreadstat")
    pd = pytest.importorskip("pandas")
    source = tmp_path / "x.zsav"
    readstat.write_sav(pd.DataFrame({"x": [0.0] * 10}), str(source), compress=True)
    from filerepack.spss import SystemFile
    from filerepack.format_support import Budget, FormatLimits

    stream = bytearray(source.read_bytes())
    parsed = SystemFile(bytes(stream), Budget(FormatLimits()))
    stream[parsed.pos + 8 : parsed.pos + 16] = struct.pack("<q", 1)
    source.write_bytes(stream)
    with pytest.raises(ValueError, match="bounds"):
        rewrite("spss", source, experimental_formats=True)
    stream[176:180] = struct.pack("<i", 45)
    source.write_bytes(stream)
    with pytest.raises(ValueError, match="unknown"):
        rewrite("spss", source, experimental_formats=True)


@pytest.mark.parametrize("damage", ["crc", "descriptor", "local-name", "directory-offset"])
def test_checkpoint_complete_framing_damage(checkpoint, damage):
    raw = bytearray(checkpoint.read_bytes())
    with zipfile.ZipFile(checkpoint) as archive:
        info = archive.infolist()[0]
        name_length, extra_length = struct.unpack_from("<HH", raw, info.header_offset + 26)
        body = info.header_offset + 30 + name_length + extra_length
        if damage == "crc":
            raw[body] ^= 1
        elif damage == "descriptor":
            raw[body + info.compress_size + 4] ^= 1
        elif damage == "local-name":
            raw[info.header_offset + 30] ^= 1
        else:
            raw[archive.start_dir + 42 : archive.start_dir + 46] = struct.pack("<I", 7)
    checkpoint.write_bytes(raw)
    with pytest.raises(ValueError):
        rewrite("checkpoint", checkpoint)


@pytest.mark.parametrize("endian", ["<", ">"])
def test_spss_ieee_endian_and_nan_signed_zero_bits(tmp_path, endian):
    reader = pytest.importorskip("pyreadstat")
    source = tmp_path / "typed.sav"
    header = (
        b"$FL2"
        + b"@(#) SPSS DATA FILE preserving fixture".ljust(60, b" ")
        + struct.pack(endian + "5id", 2, 2, 0, 0, 400, 100.0)
        + b"04 Oct 26"
        + b"00:00:00"
        + b"fixture".ljust(64, b" ")
        + b"\0" * 3
    )
    numeric_format, string_format = 5 * 65536 + 8 * 256 + 2, 65536 + 8 * 256
    dictionary = (
        struct.pack(endian + "6i8s", 2, 0, 0, 0, numeric_format, numeric_format, b"NUM     ")
        + struct.pack(endian + "6i8s", 2, 8, 0, 0, string_format, string_format, b"TEXT    ")
        + struct.pack(
            endian + "4i8i", 7, 3, 4, 8, 1, 0, 0, -1, 1, 1, 2 if endian == "<" else 1, 65001
        )
        + struct.pack(endian + "2i", 999, 0)
    )
    values = [struct.pack(endian + "d", n) for n in (0.0, -0.0, 1.0)]
    values.append(struct.pack(endian + "Q", 0x7FF8000000000012))
    raw = b"".join(value + b" " * 8 for value in values) * 100
    source.write_bytes(header + dictionary + raw)
    candidate, info = rewrite("spss", source)
    assert info["equal"] and candidate.stat().st_size < source.stat().st_size
    a, am = reader.read_sav(str(source))
    b, bm = reader.read_sav(str(candidate))
    assert a.equals(b) and am.column_names == bm.column_names


def test_mat_v73_and_unsupported_v4(tmp_path):
    h5py = pytest.importorskip("h5py")
    np = pytest.importorskip("numpy")
    if not shutil.which("h5repack"):
        pytest.skip("h5repack unavailable")
    source = tmp_path / "v73.mat"
    with h5py.File(source, "w", userblock_size=512) as f:
        x = f.create_dataset("x", data=np.zeros(2000), compression="gzip", compression_opts=1)
        x.attrs["MATLAB_class"] = b"double"
        f.create_group("#refs#").create_dataset("ref", data=[x.ref], dtype=h5py.ref_dtype)
    with source.open("r+b") as f:
        f.write(b"MATLAB 7.3 MAT-file, synthetic fixture".ljust(116, b" ") + b"\0" * 8 + b"\0\2IM")
    candidate, info = rewrite("mat", source, experimental_formats=True)
    assert info["details"]["native_reader_gate"] == "MATLAB pending"
    assert candidate.read_bytes()[:512] == source.read_bytes()[:512]
    source.write_bytes(struct.pack("<5i", 0, 10, 10, 0, 2) + b"x\0" + b"\0" * 800)
    with pytest.raises(ValueError, match="Level-5"):
        rewrite("mat", source, experimental_formats=True)


def test_scratch_supervisor_tolerates_owned_atomic_rename(tmp_path, monkeypatch):
    from filerepack import format_support

    old, new = tmp_path / "pending", tmp_path / "finished"
    old.write_bytes(b"owned chunk")
    real_getsize = os.path.getsize

    def moving(path):
        if str(path) == str(old) and old.exists():
            old.rename(new)
        return real_getsize(path)

    monkeypatch.setattr(format_support.os.path, "getsize", moving)
    format_support._scratch_size(str(tmp_path))  # First inventory contains a stale name.
    assert format_support._scratch_size(str(tmp_path)) == len(b"owned chunk")


def test_unsupported_checkpoint_in_nested_zip_keeps_member_bytes(checkpoint, tmp_path):
    inner = tmp_path / "model.zip"
    shutil.copyfile(checkpoint, inner)
    with zipfile.ZipFile(inner, "a") as z:
        z.writestr("state/code/__torch__.py", "unsupported TorchScript")
    original = inner.read_bytes()
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("model.zip", original)
    FileRepacker().repack_zip_file(str(outer))
    with zipfile.ZipFile(outer) as z:
        assert z.read("model.zip") == original


def test_r_compound_wrapper_aliases():
    from filerepack.formats import filename_exts

    kind = identify_filename("analysis.RDS.xz")
    assert kind.packer == "r-serialization"
    assert "rds" in filename_exts("analysis.RDS.xz")
