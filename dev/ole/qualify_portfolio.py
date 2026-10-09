"""Public API preservation, physical savings and passive rendering qualification."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

from filerepack import FileRepacker, RepackOptions
from filerepack.ole_verify import ole_fingerprint
from filerepack.verification import preservation_equal
from dev.ole.qualify import render
from test.ole_fixtures import ADDITIONAL_ART_ORIGINALS, CORPUS
from test.ole_art_fixtures import control
from test.test_ole_extended import (
    EXTENDED,
    HOSTS,
    duplicate_xls,
    duplicate_ppt,
    weak_hwp,
    native_zip_parent,
)
from test.test_ole_host_coverage import (
    populated_xls,
    piece_word,
    inherited_word,
    alternate_group_xls,
)


def cases():
    for name in HOSTS:
        yield name, "original", (EXTENDED / name).read_bytes(), {}
    for name in ("sample-5017-pics.hwp", "sample-5017.hwp", "pagedefs.hwp"):
        yield name, "original-recompress", (EXTENDED / name).read_bytes(), {"ole_recompress": True}
    for name in ADDITIONAL_ART_ORIGINALS:
        yield name, "original-recompress", (EXTENDED / name).read_bytes(), {"ole_recompress": True}
    for name in (
        "vector_image.doc",
        "word_with_embeded.doc",
        "SimpleWithImages.xls",
        "ole2-embedding-2003.ppt",
        "PngPicture.doc",
    ):
        for ultra in (False, True):
            yield (
                name,
                "original-" + ("maximum" if ultra else "default"),
                (CORPUS / name).read_bytes(),
                {"ole_recompress": True, "ultra": ultra},
            )
    for name, factory, options in (
        ("sample-5017-pics.hwp", weak_hwp, {"ole_recompress": True}),
        ("duplicate.xls", duplicate_xls, {"ole_deduplicate_images": True}),
        ("duplicate.ppt", duplicate_ppt, {"ole_deduplicate_images": True}),
        ("nested.doc", lambda: native_zip_parent()[0], {"ole_embedded_recompress": True}),
        ("populated.xls", populated_xls, {"ole_recompress": True}),
        ("alternate-group.xls", alternate_group_xls, {"ole_recompress": True}),
        ("pieces.doc", piece_word, {"ole_recompress": True}),
        ("inherited.doc", inherited_word, {"ole_recompress": True}),
        ("weak.doc", lambda: control("word_with_embeded.doc"), {"ole_recompress": True}),
    ):
        yield name, "controlled", factory().data, options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    writer = str(Path(args.writer).resolve())
    os.environ["FILEREPACK_OLE_COMPACTOR"] = writer
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "writer": subprocess.check_output([writer, "--version"], text=True).strip(),
        "qualified_platforms": ["macOS arm64"],
        "unavailable": ["Microsoft Office", "Hancom Office", "native Linux/Windows runs"],
        "cases": [],
    }
    if args.render:
        report["renderer"] = subprocess.check_output(["soffice", "--version"], text=True).strip()
    with tempfile.TemporaryDirectory(prefix="ole-portfolio-") as temporary:
        root = Path(temporary)
        for index, (name, variant, data, options) in enumerate(cases()):
            directory = root / str(index)
            directory.mkdir()
            before, after = directory / "before", directory / "after"
            before.mkdir()
            after.mkdir()
            source, target, baseline = (
                before / name,
                after / name,
                directory / ("baseline" + Path(name).suffix),
            )
            source.write_bytes(data)
            baseline.touch()
            subprocess.run(
                [writer, str(source), str(baseline)], check=True, capture_output=True, timeout=120
            )
            assert ole_fingerprint(str(source)) == ole_fingerprint(str(baseline))
            started = time.monotonic()
            result = (
                FileRepacker()
                .repack(str(source), outfile=str(target), options=RepackOptions(**options))
                .results[0]
            )
            seconds = time.monotonic() - started
            strategy = result.details.get("strategy", "ole-compaction")
            verifier = {
                "ole-compaction": "ole",
                "ole-officeart-recompression": "officeart",
                "ppt-ole-recompression": "ppt-ole",
                "hwp-stream-recompression": "hwp-ole",
                "ole-embedded-recompression": "ole-embedded",
                "ole-image-deduplication": "ole-dedup",
            }[strategy]
            assert preservation_equal(str(source), str(target), verifier)
            assert source.read_bytes() == data
            assert target.stat().st_size <= baseline.stat().st_size
            entry = {
                "file": name,
                "variant": variant,
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_bytes": len(data),
                "compaction_bytes": baseline.stat().st_size,
                "selected_bytes": target.stat().st_size,
                "seconds": round(seconds, 6),
                "options": options,
                "verifier": verifier,
                "preserved": True,
                "details": result.details,
            }
            if args.render and source.suffix in (".doc", ".xls", ".ppt"):
                try:
                    original_pages = render(source, before, "soffice", "pdftoppm")
                    selected_pages = render(target, after, "soffice", "pdftoppm")
                    entry["render"] = {
                        "equal": original_pages == selected_pages,
                        "pages": original_pages,
                        "candidate_pages": selected_pages,
                        "macro_security_level": 3,
                        "dpi": 96,
                    }
                    assert original_pages == selected_pages, (name, variant, "render differs")
                except RuntimeError as exc:
                    entry["render"] = {"unavailable": str(exc)}
            report["cases"].append(entry)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(
                name,
                variant,
                len(data),
                baseline.stat().st_size,
                target.stat().st_size,
                verifier,
                round(seconds, 3),
                flush=True,
            )


if __name__ == "__main__":
    main()
