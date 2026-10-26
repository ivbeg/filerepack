## Context
filerepack is a Python CLI that dispatches `pack_*()` functions and walks archive members with 7-Zip. [Chisel](https://github.com/Snesnopic/chisel) is a C++ tool that vendors encoders and treats PDFs, XML, and tagged audio as **containers**. Cloning Chisel’s processor registry or vendoring mozjpeg/libjxl/TagLib would fight this project’s packaging model.

Active related changes: `add-dicom-support` (done, unarchived) and `improve-lossy-pdf-compression` (done, unarchived). The latter explicitly deferred pikepdf image walking.

## Goals / Non-Goals
- Goals:
  - Capture Chisel’s high-value nested-asset wins using Python extras + existing packers
  - Add formats that fit current tools (ImageMagick, 7-Zip, optivorbis CLI)
  - Keep every new tool optional; missing tool ⇒ skip, original unchanged
  - Ship as sequenced phases that can land as separate PRs under this change
- Non-Goals:
  - Vendoring C++/Rust libraries or a Chisel-style `IProcessor` registry
  - PE (`.exe`/`.dll`) resource rewriting, OLE/CFBF (`.doc`/`.xls`/`.msi`; Windows-only in Chisel)
  - SWF, STL, Lua bytecode, miniSEED, Kanzi, GFT, RDB
  - MIME email (`.eml`/`.msg`/`.mht`) and vCard (`.vcf`) in v1
  - stdin/stdout, regex `--include`/`--exclude`, `--mode pipe|parallel`
  - Semantic `raw_equal()` checksums
  - Changing the lossless JPEG default (still strips unless `--keep-meta`)
  - Replacing Ghostscript `--lossy` PDF; this change only adds lossless stream walking
  - Rewriting signed installers (`.deb`/`.rpm`/`.pkg`/`.dmg`)

## Decisions

- Decision: **Virtual containers, not a processor framework.**
  Add a small `filerepack/containers.py` helper: extract nested files to a temp dir (real extensions), run the existing dispatch/deep-walk, reinsert if any member shrank, then `_commit_output` the rebuilt host file.
  - Alternatives: copy Chisel’s three-phase executor — too much C++-shaped architecture for ~three container types; or one-off extract logic in each packer — duplicates temp-dir and commit rules.

- Decision: **XML/JSON minify is a normal standalone packer** (`pack_xml`, `pack_json`).
  Once `xml`/`json` are in `STANDALONE_EXTS` and `_PACKERS`, the existing ZIP/OOXML/ODF/EPUB walk minifies them with no extra archive code.
  - JSON: `json.loads` + `json.dumps(separators=(',', ':'), ensure_ascii=False)`.
  - XML: parse with `xml.etree.ElementTree` (or `defusedxml` if we parse untrusted files from archives — prefer defusedxml for archive members), serialize without indent, **keep text-node content and `xml:space="preserve"`**. Do not collapse whitespace inside text.
  - SVG: keep `svgo`/`scour` first; `pack_xml` is the fallback when those tools are missing, and still runs data-URI extraction.

- Decision: **Cover art via `mutagen` extra `filerepack[media]`, not TagLib.**
  Extract attached pictures from MP3/FLAC/Ogg/M4A/MP4/APE (and best-effort ASF/WAV/AIFF), write them as `.jpg`/`.png`/`.webp`, run existing image packers, write tags back. Audio **codec** paths (flac, mp3packer, alac) stay unchanged and run after or before cover rewrite; commit the smallest valid result that still plays.
  - If mutagen is not installed, skip cover extraction (same as missing jpegoptim).

- Decision: **PDF stream walking via `pikepdf` extra `filerepack[pdf]`.**
  Lossless default remains qpdf. When pikepdf is installed and `--lossy` is off, extract image streams (DCT / JPX / Flate-as-PNG) to temp files, pack them, replace streams, then run qpdf linearize on the rebuilt file. Ghostscript `--lossy` / `--pdf-profile` path is untouched.
  - This is the follow-on called out in `improve-lossy-pdf-compression`.
  - Skip signed PDFs (`/Encrypt`, `/Perms`, or signature dictionaries) fail-closed.

- Decision: **Encoder upgrades are prefer-if-present, not hard deps.**
  JPEG: `jpegtran -optimize -progressive` (mozjpeg or libjpeg-turbo) then existing `jpegoptim`. Strip vs keep follows `--keep-meta`.
  PNG: keep oxipng/optipng; if `zopflipng` is on PATH and `--ultra` is set, try it and keep the smallest.
  GIF FlexiGif: skip (unpackaged). gifsicle stays.

- Decision: **`--keep-meta` default false** (current JPEG `--strip-all` / oxipng `--strip safe`).
  When true: jpegoptim without `--strip-all`, jpegtran `-copy all`, oxipng without `--strip`. Not a global Chisel `--no-meta` inverse; video/pdf tools keep today’s metadata behavior.

- Decision: **Ogg Vorbis/Opus via optional `optivorbis` CLI**, registered like `mp3packer`.
  `.ogg` / `.opus` are new standalone keys. `.oga` stays FLAC-in-Ogg via ffmpeg; if the stream is Vorbis/Opus, route to optivorbis instead of failing the FLAC allow-list.
  Cover art for those files still goes through mutagen.

- Decision: **Cheap formats only when a current tool can round-trip.**
  - Aliases: `.db` → sqlite; `.apng` → png; `.cur` → ico; JPEG `.jif`/`.jfi`/`.thm`; `.m4b` → m4a cover+alac path as appropriate; ZIP aliases listed in the formats spec.
  - BMP/TGA/PNM/PCX: ImageMagick lossless recompress (`magick` already used for TIFF/ICO). Skip if `convert` is missing.
  - ISO/CPIO/AR: extract with 7zz **only if 7zz can write the same family back**. If write is unsupported (typical for ISO), do not pretend to support the format. Confirm during Phase 8; drop from scope if round-trip fails.

- Decision: **Do not add `.deb`/`.ipk`** even though Chisel lists them. Signed packages stay skipped.

## Risks / Trade-offs
- OOXML XML minify can break unusual documents if whitespace in `w:t` is destroyed → Mitigation: never rewrite text-node character data; only drop ignorable whitespace between elements; tests on a real docx/xlsx/pptx.
- mutagen tag rewrite can drop unknown frames → Mitigation: load/save in-place with mutagen’s existing files; tests that ID3 frames besides APIC survive.
- pikepdf stream replace can desync `/Length` or filters → Mitigation: let pikepdf rewrite the stream object; qpdf verify after; skip on exception.
- mozjpeg `jpegtran` vs libjpeg-turbo `jpegtran` behave differently → Mitigation: treat any `jpegtran` as optional optimize; still require output smaller + JPEG magic.
- Cover-art + codec pack on the same MP3 could race or double-write → Mitigation: one `pack_mp3` pipeline: covers first, then mp3packer on the tagged file (or the reverse if packing first yields smaller frames); single commit.
- Extra deps (`mutagen`, `pikepdf`) surprise users who pip-install the base package → Mitigation: extras; doctor/docs; skip if import fails.

## Migration Plan
- Additive. New extensions start being processed when tools/extras exist.
- JPEG/PNG output without `--keep-meta` stays as today.
- Rollback: remove packers/extras; no on-disk format migration.

## Open Questions
- Phase 8 ISO/CPIO/AR: confirm 7zz write support on macOS/Linux/Windows before implementing; otherwise cut.
- Whether `--keep-meta` should also disable svgo/scour metadata stripping (lean no for v1).
- Audiobook `.m4b` as ALAC recompress vs cover-only (lean: cover + existing m4a ALAC path when codec is alac).
