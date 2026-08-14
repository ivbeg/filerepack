## 1. Shared container helper
- [x] 1.1 Add `filerepack/containers.py`: extract members to a temp dir, run existing packer dispatch on each file, report whether anything shrank
- [x] 1.2 Reinsert helper takes a mapping of original member → packed path and leaves the host file rebuild to the caller
- [x] 1.3 Unit tests: no-op when no member is smaller; temp dir cleaned on success and on exception

## 2. Phase 1 — XML and JSON minify
- [x] 2.1 Add `xml`, `json`, and XML aliases (`xhtml`, `kml`, `gpx`, `dae`, `rss`, `atom`, `xmp`, `xsl`, `xslt`, `fb2`) to `STANDALONE_EXTS` and `_PACKERS` (category `document`)
- [x] 2.2 Implement `pack_json`: compact UTF-8 JSON; skip invalid JSON
- [x] 2.3 Implement `pack_xml`: minify without changing text-node content; honor `xml:space="preserve"`
- [x] 2.4 SVG: keep svgo/scour first; use `pack_xml` as fallback
- [x] 2.5 Tests: pretty JSON shrinks; invalid JSON skipped; OOXML `w:t` text preserved on a fixture docx after nested walk
- [x] 2.6 Docs + CHANGELOG: XML/JSON inside ZIP/OOXML/ODF/EPUB

## 3. Phase 2 — Cover art (`filerepack[media]`)
- [x] 3.1 Add optional extra `media` → `mutagen>=1.47`
- [x] 3.2 Extract attached pictures from MP3, FLAC, Ogg, M4A/MP4, APE; write as jpg/png/webp; dispatch image packers; write tags back
- [x] 3.3 If mutagen is missing, skip cover extraction; codec packers still run
- [x] 3.4 Combine with existing `pack_mp3` / `pack_flac` / `pack_m4a` / `pack_ape` so one commit wins
- [x] 3.5 Tests: missing mutagen → None for covers; mocked picture round-trip; non-APIC ID3 frames survive
- [x] 3.6 Docs: extra, formats that get cover walking

## 4. Phase 3 — Encoder quality and `--keep-meta`
- [x] 4.1 Register optional `jpegtran` and `zopflipng` in `TOOL_SPECS` + install hints (mozjpeg / jpeg / zopflipng)
- [x] 4.2 JPEG lossless: try `jpegtran -optimize -progressive` then `jpegoptim`; `--keep-meta` uses `-copy all` / no `--strip-all`
- [x] 4.3 PNG: oxipng/optipng as today; `--ultra` also tries zopflipng and keeps the smallest
- [x] 4.4 Add `RepackOptions.keep_meta` and CLI `--keep-meta` (default false)
- [x] 4.5 Tests: keep-meta omits strip flags; jpegtran missing falls back to jpegoptim; ultra PNG tries zopflipng when present
- [x] 4.6 Docs: tool table, `--keep-meta`, `--ultra` PNG

## 5. Phase 4 — Cheap aliases
- [x] 5.1 SQLite: `.db` alias (magic still required)
- [x] 5.2 Images: `.apng` → png, `.cur` → ico, `.jif`/`.jfi`/`.thm` → jpg
- [x] 5.3 Audio: `.ogg`/`.opus` identification (packer wired in Phase 6); `.m4b` → m4a path
- [x] 5.4 ZIP aliases from the formats spec (only names 7-Zip already extracts as ZIP)
- [x] 5.5 Tests for `identify_filename` / `--include-ext` aliases
- [x] 5.6 README formats table

## 6. Phase 5 — Raster formats via ImageMagick
- [x] 6.1 `pack_bmp`, `pack_tga`, `pack_pnm`, `pack_pcx` using existing `_pack_magick` lossless path
- [x] 6.2 Extensions: bmp/dib, tga/targa, pnm/ppm/pgm/pbm, pcx/dcx
- [x] 6.3 Skip when `convert`/`magick` is missing
- [x] 6.4 Tests: missing tool; dispatch category `image` honors `--no-images`
- [x] 6.5 Docs + doctor purpose text if needed

## 7. Phase 6 — Ogg Vorbis / Opus
- [x] 7.1 Register `optivorbis` (`FILEREPACK_OPTIVORBIS`) like mp3packer; doctor + install notes (GitHub CLI zips, not Cargo/Homebrew)
- [x] 7.2 `pack_ogg` / `.opus`: run optivorbis; leave file unchanged if tool missing
- [x] 7.3 `.oga`: if stream is FLAC keep ffmpeg path; if Vorbis/Opus route to optivorbis
- [x] 7.4 Cover art (Phase 2) still applies
- [x] 7.5 Tests: missing tool; `--no-images` still skips audio (existing category rule)
- [x] 7.6 Docs

## 8. Phase 7 — PDF stream walking (`filerepack[pdf]`)
- [x] 8.1 Extra `pdf` → `pikepdf>=8`
- [x] 8.2 When pikepdf is installed and lossless PDF (no `--lossy` / `--pdf-profile` / `--jpeg-quality`): extract DCT/JPX/PNG-like streams, pack, replace, then qpdf linearize
- [x] 8.3 Skip encrypted or signed PDFs
- [x] 8.4 Ghostscript lossy path unchanged
- [x] 8.5 Tests: no pikepdf → qpdf-only; signed/encrypted skipped; mocked smaller JPEG stream is injected
- [x] 8.6 Docs: extra, relationship to `--lossy`

## 9. Phase 8 — ISO / CPIO / AR (conditional)
- [x] 9.1 Probe 7zz write support for iso/cpio/ar on CI platforms
- [x] 9.2 If write works: add families, extract+walk+rewrite like tar
- [x] 9.3 If write fails: document as out of scope and skip this phase — 7zz cannot create ISO/CPIO/AR
- [x] 9.4 Tests only if implemented (skipped)

## 10. Docs and validation
- [x] 10.1 README formats table + extras (`media`, `pdf`)
- [x] 10.2 `docs/cli.md`, `docs/tools.md`, `docs/library.md` (`keep_meta`, extras)
- [x] 10.3 CHANGELOG
- [x] 10.4 `make test` and `make lint`
- [x] 10.5 `openspec validate add-chisel-parity --strict`
