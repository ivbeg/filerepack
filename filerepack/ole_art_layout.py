"""Host adapters and a distinct intended-change contract for OfficeArt."""

import io
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Tuple, Union

from .format_support import Budget, FormatLimit
from .ole_officeart import Parser, Record, encode_metafiles, encode_rasters, require
from .ole_verify import CompoundFile, OleManifest
from .ole_verify import independent_manifest
from .ole_ppt_art import PptArt
from .ole_word_art import WordArt
from .ole_word_floating import FloatingWordArt
from .ole_xls_art import XlsArt

Adapter = Union[WordArt, FloatingWordArt, XlsArt, PptArt]


@dataclass(frozen=True)
class ArtSource:
    """Retain verified metadata/sizes, not another full CFB allocation carrier."""

    manifest: OleManifest
    stream_sizes: Dict[Tuple[str, ...], int]


@dataclass(frozen=True)
class ArtIdentity:
    content: Tuple[object, ...]
    raster_sizes: Tuple[int, ...]
    metafile_sizes: Tuple[int, ...]


@dataclass
class ArtLayout:
    compound: ArtSource
    host: str
    adapter: Adapter
    metafiles: List[Record]
    rasters: List[Record]
    raster_skips: List[str]

    def fingerprint(self) -> Tuple[object, ...]:
        changed = {
            "doc": {("WordDocument",), ("Data",)},
            "xls": {("Workbook",)},
            "ppt": {("PowerPoint Document",), ("Pictures",)},
        }[self.host]
        if isinstance(self.adapter, (WordArt, FloatingWordArt)):
            changed = self.adapter.changed
        entries = tuple(
            replace(e, size=0, sha256="") if e.path in changed else e
            for e in self.compound.manifest.entries
        )
        return self.host, entries, self.adapter.fingerprint()

    def identity(self) -> ArtIdentity:
        return ArtIdentity(
            self.fingerprint(),
            tuple(len(r.raster.encoded) for r in self.rasters if r.raster is not None),
            tuple(len(r.metafile.encoded) for r in self.metafiles if r.metafile is not None),
        )

    def reencode(
        self, budget: Budget, ultra: bool = False
    ) -> Tuple[Dict[Tuple[str, ...], bytes], Dict[str, Any]]:
        from .ole_officeart import _zopfli

        optional = _zopfli() is not None
        payloads, encoders = encode_metafiles(self.metafiles, budget, ultra)
        images, image_encoders = encode_rasters(self.rasters, budget, ultra, self.raster_skips)
        payloads.update(images)
        replacements = self.adapter.rebuild(payloads)
        types = ["EMF" if record.kind == 0xF01A else "WMF" for record in self.metafiles]
        return replacements, {
            "officeart_host": self.host,
            "metafile_count": len(types),
            "metafile_types": types,
            "encoders": encoders,
            "raster_count": len(self.rasters),
            "raster_encoders": image_encoders,
            "raster_skips": self.raster_skips,
            "recompressed_rasters": sum(not e.startswith("original") for e in image_encoders),
            "ole_effort_version": 1,
            "ole_effort": "maximum" if ultra else "default",
            "zopfli_version": "0.4.3" if optional else None,
            "effort_note": "qualified Zopfli trials available"
            if optional
            else "Zopfli 0.4.3 unavailable; original/zlib9 trials only",
            "recompressed_metafiles": sum(e != "original" for e in encoders),
            "decoded_metafile_bytes": sum(
                len(r.metafile.raw) for r in self.metafiles if r.metafile is not None
            ),
            "stream_savings_bytes": sum(
                self.compound.stream_sizes[p] - len(data) for p, data in replacements.items()
            ),
        }


def inspect_art(compound: CompoundFile, budget: Budget, *, pack_images: bool = True) -> ArtLayout:
    from .ole import _profile
    from .ole_ppt_art import inspect_ppt
    from .ole_word_art import WORD, inspect_word
    from .ole_xls_art import WORKBOOK, inspect_xls

    profiles = [
        host
        for host, path in (("doc", WORD), ("xls", WORKBOOK), ("ppt", ("PowerPoint Document",)))
        if path in compound.streams
    ]
    require(len(profiles) == 1, "unknown/ambiguous OLE application")
    host = profiles[0]
    require(_profile(compound, host) == (host, False), "host macros are not qualified")
    independent_manifest(io.BytesIO(compound.data), compound)
    budget.consume(nodes=len(compound.entries))
    parser = Parser(
        budget, raster=pack_images, bounded_png=host in {"doc", "ppt"},
        word_properties=host == "doc",
    )
    adapter: Adapter
    if host == "doc":
        try:
            adapter = inspect_word(compound, parser)
        except FormatLimit:
            raise
        except ValueError as inline_error:
            from .ole_word_floating import inspect_floating

            parser = Parser(budget, raster=pack_images, bounded_png=True, word_properties=True)
            try:
                adapter = inspect_floating(compound, parser)
            except FormatLimit:
                raise
            except ValueError as floating_error:
                raise ValueError(
                    f"Word inline pictures: {inline_error}; "
                    f"Word floating pictures: {floating_error}"
                ) from floating_error
    elif host == "xls":
        adapter = inspect_xls(compound.streams[WORKBOOK], parser)
    else:
        adapter = inspect_ppt(compound, parser)
    require(bool(parser.metafiles or parser.rasters), "no qualified OfficeArt picture payloads")
    if not pack_images:
        require(False, "parent policy disables OfficeArt image optimization")
    source = ArtSource(
        compound.manifest, {path: len(data) for path, data in compound.streams.items()}
    )
    return ArtLayout(source, host, adapter, parser.metafiles, parser.rasters, parser.raster_skips)


def equal_art(source: Union[ArtLayout, ArtIdentity], candidate: ArtLayout) -> bool:
    before = source.identity() if isinstance(source, ArtLayout) else source
    after = candidate.identity()
    return (
        before.content == after.content
        and len(before.raster_sizes) == len(after.raster_sizes)
        and len(before.metafile_sizes) == len(after.metafile_sizes)
        and all(a <= b for a, b in zip(after.raster_sizes, before.raster_sizes))
        and all(a <= b for a, b in zip(after.metafile_sizes, before.metafile_sizes))
    )
