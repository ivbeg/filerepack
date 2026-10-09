"""Typed HDF5 graph and raw NetCDF comparisons, with preserving native writers."""

import hashlib
import itertools
import os
import subprocess
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .format_support import Budget, UnsupportedFormat
from .tools import resolve_tool


def slices(shape: Tuple[int, ...], itemsize: int, budget: Budget) -> Iterator[Any]:
    if not shape:
        yield ()
        return
    if any(length == 0 for length in shape):
        return
    # Bound a hyperslab even for a very wide single row.
    capacity = max(1, min(1024 * 1024, budget.limits.memory // 16) // max(1, itemsize))
    geometry = [1] * len(shape)
    for axis in reversed(range(len(shape))):
        geometry[axis] = min(shape[axis], capacity)
        capacity = max(1, capacity // geometry[axis])
    for starts in itertools.product(
        *(range(0, length, width) for length, width in zip(shape, geometry))
    ):
        yield tuple(
            slice(start, min(start + width, length))
            for start, width, length in zip(starts, geometry, shape)
        )


def _address(value: Any, h5py: Any) -> int:
    return int(h5py.h5o.get_info(value.id).addr)


def _region(value: Any, file: Any, h5py: Any, budget: Budget) -> Any:
    space = h5py.h5r.get_region(value, file.id)
    selection = space.get_select_type()
    budget.consume(nodes=1)
    if selection == h5py.h5s.SEL_POINTS:
        budget.consume(nodes=space.get_select_npoints())
        return selection, space.get_select_elem_pointlist().tolist()
    if selection == h5py.h5s.SEL_HYPERSLABS:
        budget.consume(nodes=space.get_select_hyper_nblocks())
        return selection, space.get_select_hyper_blocklist().tolist()
    return selection, space.get_simple_extent_dims()


def _typed(value: Any, dtype: Any, file: Any, identities: Dict[int, str], budget: Budget) -> Any:
    import h5py
    import numpy as np

    array = np.asarray(value, dtype=dtype)
    if not array.dtype.hasobject:
        # Compound padding may be undefined during H5Dread. Refuse it instead of
        # accidentally comparing freshly allocated padding bytes.
        if array.dtype.fields:
            ranges = sorted(
                (field[1], field[1] + field[0].itemsize) for field in array.dtype.fields.values()
            )
            if (
                ranges[0][0] != 0
                or ranges[-1][1] != array.dtype.itemsize
                or any(a[1] != b[0] for a, b in zip(ranges, ranges[1:]))
            ):
                raise UnsupportedFormat("padded compound HDF5 types are outside the profile")
        budget.consume(decoded=array.nbytes)
        return hashlib.sha256(array.tobytes(order="C")).hexdigest()
    result: List[Any] = []
    if array.dtype.fields:
        for name in array.dtype.names:
            result.append(
                (name, _typed(array[name], array.dtype.fields[name][0], file, identities, budget))
            )
        return result
    for entry in array.flat:
        budget.consume(nodes=1)
        if entry is None and h5py.check_dtype(ref=dtype) is not None:
            result.append(("null-reference",))
        elif isinstance(entry, h5py.Reference):
            if not entry:
                result.append(("null-reference",))
                continue
            target = file[entry]
            identity = identities.get(_address(target, h5py))
            if identity is None:
                raise UnsupportedFormat("reference to an unlinked/unknown HDF5 object")
            region = (
                _region(entry, file, h5py, budget)
                if isinstance(entry, h5py.RegionReference)
                else None
            )
            result.append(("reference", identity, region))
        elif isinstance(entry, (str, bytes)):
            raw = entry.encode("utf-8") if isinstance(entry, str) else entry
            budget.consume(decoded=len(raw))
            result.append(("string", hashlib.sha256(raw).hexdigest()))
        elif isinstance(entry, np.ndarray):
            result.append(
                (
                    "vlen",
                    entry.dtype.str,
                    tuple(entry.shape),
                    _typed(entry, entry.dtype, file, identities, budget),
                )
            )
        else:
            raise UnsupportedFormat("unsupported HDF5 variable-length element")
    return result


def _attrs(obj: Any, file: Any, identities: Dict[int, str], budget: Budget) -> Any:
    attrs = []
    for name in obj.attrs:
        budget.consume(nodes=1)
        identity = obj.attrs.get_id(name)
        space = identity.get_space()
        shape = space.get_simple_extent_dims()
        dtype = identity.dtype
        budget.memory(max(1, space.get_simple_extent_npoints()) * max(1, dtype.itemsize))
        attrs.append(
            (
                name,
                identity.get_type().encode().hex(),
                shape,
                _typed(obj.attrs[name], dtype, file, identities, budget),
            )
        )
    flags = obj.id.get_create_plist().get_attr_creation_order()
    return flags, attrs if flags else sorted(attrs)


def _hdf_graph(file: Any, budget: Budget) -> Tuple[Dict[int, str], List[Any], List[Any]]:
    import h5py

    identities: Dict[int, str] = {}
    objects: List[Any] = []
    links: List[Any] = []

    def visit(obj: Any, path: str) -> None:
        address = _address(obj, h5py)
        if address in identities:
            return
        budget.consume(nodes=1)
        identities[address] = path
        objects.append((path, obj))
        if not isinstance(obj, h5py.Group):
            return
        for name in sorted(obj.keys()):
            budget.consume(nodes=1)
            link = obj.get(name, getlink=True)
            childpath = path.rstrip("/") + "/" + name
            if isinstance(link, h5py.SoftLink):
                links.append((childpath, "soft", link.path))
            elif isinstance(link, h5py.ExternalLink):
                links.append((childpath, "external", link.filename, link.path))
            elif isinstance(link, h5py.HardLink):
                target = obj[name]
                visit(target, childpath)
                links.append((childpath, "hard", identities[_address(target, h5py)]))
            else:
                raise UnsupportedFormat("unknown HDF5 link class")

    visit(file["/"], "/")
    return identities, objects, sorted(links)


def _hdf_storage(obj: Any) -> Any:
    plist = obj.id.get_create_plist()
    filters = []
    for index in range(plist.get_nfilters()):
        identity, flags, parameters, name = plist.get_filter(index)
        if identity not in (1, 2, 3):
            raise UnsupportedFormat("unsupported/lossy HDF5 filter pipeline")
        filters.append((identity, flags, () if identity == 1 else tuple(parameters)))
    return filters, obj.chunks


def hdf_manifest(path: str, budget: Budget) -> Tuple[Any, List[Tuple[str, Any]]]:
    import h5py

    with h5py.File(path, "r") as file:
        identities, objects, links = _hdf_graph(file, budget)
        manifest: List[Any] = []
        datasets: List[Tuple[str, Any]] = []
        for name, obj in objects:
            attributes = _attrs(obj, file, identities, budget)
            if isinstance(obj, h5py.Group):
                plist = obj.id.get_create_plist()
                order = plist.get_link_creation_order()
                manifest.append(
                    (
                        name,
                        "group",
                        order,
                        list(obj.keys()) if order else sorted(obj.keys()),
                        attributes,
                    )
                )
            elif isinstance(obj, h5py.Datatype):
                manifest.append((name, "datatype", obj.id.encode().hex(), attributes))
            elif isinstance(obj, h5py.Dataset):
                if obj.external or obj.is_virtual or obj.shape is None:
                    raise UnsupportedFormat("external, virtual or null HDF5 dataset")
                storage = _hdf_storage(obj)
                datatype = obj.id.get_type()
                committed = (
                    identities.get(h5py.h5o.get_info(datatype).addr)
                    if (datatype.committed())
                    else None
                )
                if datatype.committed() and committed is None:
                    raise UnsupportedFormat("unlinked committed HDF5 datatype")
                if obj.chunks:
                    chunk_bytes = obj.dtype.itemsize
                    for length in obj.chunks:
                        chunk_bytes *= length
                    budget.memory(chunk_bytes)
                values = []
                for section in slices(obj.shape, obj.dtype.itemsize, budget):
                    values.append(_typed(obj[section], obj.dtype, file, identities, budget))
                manifest.append(
                    (
                        name,
                        "dataset",
                        tuple(obj.shape),
                        obj.maxshape,
                        datatype.encode().hex(),
                        committed,
                        attributes,
                        _typed(obj.fillvalue, obj.dtype, file, identities, budget),
                        values,
                    )
                )
                datasets.append((name, storage))
            else:
                raise UnsupportedFormat("unknown HDF5 graph object")
        user = hashlib.sha256()
        with open(path, "rb") as stream:
            remaining = file.userblock_size
            while remaining:
                raw = stream.read(min(remaining, 65536))
                if not raw:
                    raise ValueError("truncated HDF5 user block")
                user.update(raw)
                budget.consume(decoded=len(raw))
                remaining -= len(raw)
            if stream.read(8) != b"\x89HDF\r\n\x1a\n":
                raise ValueError("invalid HDF5 signature at user-block boundary")
            superblock = stream.read(1)
        return (file.userblock_size, user.hexdigest(), superblock.hex(), manifest, links), datasets


def _storage_equal(left: Any, right: Any) -> bool:
    if len(left) != len(right):
        return False
    for (name, (filters, chunks)), (other, (newfilters, newchunks)) in zip(left, right):
        if name != other:
            return False
        if chunks is not None and chunks != newchunks:
            return False
        if filters:
            if filters != newfilters:
                return False
        elif any(item[0] not in (1, 2) for item in newfilters):
            return False
    return True


def _hdf_rewrite(source: str, candidate: str, datasets: Any, budget: Budget) -> None:
    import h5py

    tool = resolve_tool("h5repack")
    if not tool:
        raise UnsupportedFormat("h5repack is unavailable")
    command = [tool]
    with h5py.File(source, "r") as file:
        with open(source, "rb") as stream:
            stream.seek(file.userblock_size + 8)
            version = stream.read(1)[0]
        command.extend(["--low=0", "--high=" + ("1" if version < 3 else "2")])
        if file.userblock_size:
            command.extend(["-u", source, "-b", str(file.userblock_size)])
    for name, (filters, chunks) in datasets:
        if any(character in name for character in ":,"):
            raise UnsupportedFormat("HDF5 name cannot be selected unambiguously by h5repack")
        if filters and not any(item[0] == 1 for item in filters):
            continue
        pipeline = [item[0] for item in filters] or [1]
        for identity in pipeline:
            command.extend(["-f", name + ":" + {1: "GZIP=9", 2: "SHUF", 3: "FLET"}[identity]])
    if len(command) == 1:
        raise UnsupportedFormat("no eligible HDF5 compression candidate")
    if os.path.exists(candidate):
        os.unlink(candidate)
    command.extend([os.path.abspath(source), candidate])
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=budget.remaining()["seconds"],
    )
    if result.returncode:
        raise UnsupportedFormat("h5repack failed: " + result.stderr[:1024].decode(errors="replace"))
    budget.consume(written=os.path.getsize(candidate))


def _nc_attrs(obj: Any, budget: Budget) -> Any:
    import numpy as np

    result: List[Any] = []
    for name in obj.ncattrs():
        budget.consume(nodes=1)
        value = obj.getncattr(name)
        if isinstance(value, str):
            budget.consume(decoded=len(value.encode()))
            token: Any = ("text", value)
        else:
            array = np.asarray(value)
            if array.dtype.hasobject:
                raise UnsupportedFormat("unsupported NetCDF attribute type")
            budget.consume(decoded=array.nbytes)
            token = (array.dtype.str, tuple(array.shape), array.tobytes().hex())
        result.append((name, token))
    return result


def _nc_groups(root: Any) -> Iterator[Any]:
    yield root
    for group in root.groups.values():
        yield from _nc_groups(group)


def netcdf_manifest(path: str, budget: Budget) -> Any:
    import netCDF4

    with netCDF4.Dataset(path, "r") as file:
        if file.disk_format != "HDF5" or file.data_model not in ("NETCDF4", "NETCDF4_CLASSIC"):
            raise UnsupportedFormat("classic CDF compression requires format conversion; retained")
        file.set_auto_maskandscale(False)
        file.set_auto_chartostring(False)
        groups, storage = [], []
        for group in _nc_groups(file):
            budget.consume(nodes=1)
            if group.cmptypes or group.vltypes or group.enumtypes:
                raise UnsupportedFormat("NetCDF user-defined types are outside the initial profile")
            dims = [(name, len(dim), dim.isunlimited()) for name, dim in group.dimensions.items()]
            variables = []
            for name, variable in group.variables.items():
                budget.consume(nodes=1)
                if variable.dtype is str or variable.dtype.hasobject:
                    raise UnsupportedFormat(
                        "NetCDF NC_STRING/vlen variables are outside the profile"
                    )
                filters = variable.filters() or {}
                storage.append(
                    (
                        group.path + "/" + name,
                        variable.chunking(),
                        bool(filters.get("shuffle")),
                        bool(filters.get("fletcher32")),
                    )
                )
                if (
                    any(
                        value
                        for key, value in filters.items()
                        if key in ("szip", "zstd", "bzip2", "blosc")
                    )
                    or variable.quantization()
                ):
                    raise UnsupportedFormat("unsupported or quantized NetCDF storage")
                if variable.get_fill_value() is None:
                    raise UnsupportedFormat(
                        "NetCDF no-fill state cannot be preserved by this profile"
                    )
                values = []
                for section in slices(variable.shape, variable.dtype.itemsize, budget):
                    array = variable[section]
                    budget.consume(decoded=array.nbytes)
                    values.append(hashlib.sha256(array.tobytes(order="C")).hexdigest())
                bindings = [(dim.group().path, dim.name) for dim in variable.get_dims()]
                variables.append(
                    (
                        name,
                        variable.dtype.str,
                        tuple(variable.shape),
                        bindings,
                        variable.endian(),
                        _nc_attrs(variable, budget),
                        values,
                    )
                )
            groups.append((group.path, dims, _nc_attrs(group, budget), variables))
        return file.data_model, file.disk_format, groups, storage


def _nc_storage_equal(left: Any, right: Any) -> bool:
    if len(left) != len(right):
        return False
    for old, new in zip(left, right):
        if old[0] != new[0] or old[2:] != new[2:]:
            return False
        if isinstance(old[1], list) and old[1] != new[1]:
            return False
    return True


def _netcdf_rewrite(source: str, candidate: str, budget: Budget) -> None:
    import netCDF4

    with netCDF4.Dataset(source, "r") as original:
        original.set_auto_maskandscale(False)
        original.set_auto_chartostring(False)
        with netCDF4.Dataset(candidate, "w", format=original.data_model) as output:
            mapped = {"/": output}
            for group in _nc_groups(original):
                target = mapped[group.path]
                for name, child in group.groups.items():
                    mapped[child.path] = target.createGroup(name)
                target.setncatts({name: group.getncattr(name) for name in group.ncattrs()})
                for name, dim in group.dimensions.items():
                    target.createDimension(name, None if dim.isunlimited() else len(dim))
                for name, var in group.variables.items():
                    chunking = var.chunking()
                    filters = var.filters() or {}
                    keywords: Dict[str, Any] = {"endian": var.endian()}
                    if var.ndim:
                        keywords.update(
                            compression="zlib",
                            complevel=9,
                            shuffle=bool(filters.get("shuffle")),
                            fletcher32=bool(filters.get("fletcher32")),
                        )
                        if isinstance(chunking, list):
                            keywords["chunksizes"] = chunking
                    if "_FillValue" in var.ncattrs():
                        keywords["fill_value"] = var.getncattr("_FillValue")
                    created = target.createVariable(name, var.dtype, var.dimensions, **keywords)
                    created.set_auto_maskandscale(False)
                    created.set_auto_chartostring(False)
                    created.setncatts(
                        {
                            attr: var.getncattr(attr)
                            for attr in var.ncattrs()
                            if attr != "_FillValue"
                        }
                    )
                    for section in slices(var.shape, var.dtype.itemsize, budget):
                        data = var[section]
                        budget.consume(decoded=data.nbytes)
                        created[section] = data
            output.sync()
    budget.consume(written=os.path.getsize(candidate))
    with netCDF4.Dataset(source) as left, netCDF4.Dataset(candidate) as right:
        for group in _nc_groups(left):
            new = right if group.path == "/" else right[group.path]
            for name, var in group.variables.items():
                if isinstance(var.chunking(), list) and var.chunking() != new[name].chunking():
                    raise ValueError("NetCDF chunk geometry changed")


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    if kind == "hdf5-native":
        fingerprint, storage = hdf_manifest(source, budget)
        details = {
            "profile": "HDF5-native-DEFLATE",
            "datasets": len(storage),
            "reader_lineage": "h5py/libhdf5; separate from h5repack invocation",
        }
        if action == "inspect":
            return {"details": details}
        if action == "rewrite":
            assert candidate is not None
            _hdf_rewrite(source, candidate, storage, budget)
        other, newstorage = hdf_manifest(candidate or "", budget)
        if fingerprint != other or not _storage_equal(storage, newstorage):
            raise ValueError("HDF5 graph, type, metadata, values or compatible storage changed")
    else:
        fingerprint = netcdf_manifest(source, budget)
        details = {"profile": fingerprint[0], "reader_lineage": "netCDF4/netcdf-c raw values"}
        if action == "inspect":
            return {"details": details}
        if action == "rewrite":
            assert candidate is not None
            _netcdf_rewrite(source, candidate, budget)
        other = netcdf_manifest(candidate or "", budget)
        if fingerprint[:3] != other[:3] or not _nc_storage_equal(fingerprint[3], other[3]):
            raise ValueError("NetCDF model, dimensions, raw values or typed metadata changed")
    return {"changed": action == "rewrite", "equal": True, "details": details}
