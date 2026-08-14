## ADDED Requirements

### Requirement: SQLite .db Alias
The system SHALL treat `.db` as a SQLite alias for identification and `--include-ext` filters. `pack_sqlite` SHALL still require the `SQLite format 3` header before rewriting.

#### Scenario: .db identifies as sqlite
- **WHEN** `identify_filename` is called with `notes.db`
- **THEN** it returns a standalone kind whose packer key is `sqlite`

#### Scenario: non-SQLite .db
- **WHEN** `notes.db` does not start with `SQLite format 3`
- **THEN** `pack_sqlite` returns `None`

### Requirement: Image Extension Aliases
The system SHALL map `.apng` to the PNG packer, `.cur` to the ICO packer, and `.jif` / `.jfi` / `.thm` to the JPEG packer. `--include-ext png` SHALL match `.apng`; `--include-ext jpg` SHALL match `.thm`.

#### Scenario: APNG uses PNG packer
- **WHEN** `identify_filename` is called with `icon.apng`
- **THEN** the packer key is `png`

#### Scenario: CUR uses ICO packer
- **WHEN** `identify_filename` is called with `pointer.cur`
- **THEN** the packer key is `ico`

### Requirement: ImageMagick Raster Formats
The system SHALL treat BMP (`.bmp`, `.dib`), TGA (`.tga`, `.targa`), PNM (`.pnm`, `.ppm`, `.pgm`, `.pbm`), and PCX (`.pcx`, `.dcx`) as standalone images packed via the existing ImageMagick lossless path. Missing `magick`/`convert` SHALL skip these files. `--no-images` SHALL skip them.

#### Scenario: BMP with ImageMagick
- **WHEN** `pack_bmp` is given a BMP and ImageMagick is available
- **THEN** it losslessly recompresses to a temp BMP
- **AND** a smaller valid BMP is committed when commit rules pass

#### Scenario: tool missing
- **WHEN** ImageMagick is not available
- **THEN** BMP/TGA/PNM/PCX packers return `None`

### Requirement: Ogg Vorbis and Opus
The system SHALL treat `.ogg` and `.opus` as standalone audio. When `optivorbis` is available, the packer SHALL losslessly rewrite Vorbis/Opus streams. Missing `optivorbis` SHALL leave the file unchanged. `.oga` SHALL keep the existing FLAC-in-Ogg ffmpeg path when the codec is FLAC; Vorbis/Opus `.oga` SHALL use optivorbis instead. `optivorbis` SHALL appear in `filerepack doctor` as optional.

#### Scenario: ogg with optivorbis
- **WHEN** `pack_ogg` is given a Vorbis `.ogg` and optivorbis is on PATH
- **THEN** optivorbis writes a temp file
- **AND** a smaller valid Ogg is committed when commit rules pass

#### Scenario: optivorbis missing
- **WHEN** optivorbis is not available
- **THEN** the `.ogg` file is not replaced by the Vorbis packer

#### Scenario: oga FLAC unchanged path
- **WHEN** `.oga` contains FLAC
- **THEN** the existing ffmpeg FLAC path is used

### Requirement: M4B Alias
The system SHALL treat `.m4b` as an alias of the M4A packer path (ALAC recompress when applicable, plus cover-art extraction when mutagen is available).

#### Scenario: m4b identifies as m4a
- **WHEN** `identify_filename` is called with `book.m4b`
- **THEN** the packer key is `m4a`

### Requirement: Additional ZIP Aliases
The system SHALL treat the following extensions as ZIP-family archives (extract, deep-walk, rewrite with the existing ZIP writer): `.air`, `.pk3`, `.xap`, `.vsix` (already present), `.nupkg` (already present), `.ipsw`, `.osk`, `.oex`, `.puz`, `.rmskin`, `.notebook`, `.nbk`. Signed installers `.deb` and `.rpm` SHALL remain unsupported.

#### Scenario: pk3 is a zip archive
- **WHEN** `identify_filename` is called with `pak.pk3`
- **THEN** it returns a kind whose family is `zip`

#### Scenario: deb still skipped
- **WHEN** `identify_filename` is called with `pkg.deb`
- **THEN** it returns `None` or the file is not rewritten as a ZIP

### Requirement: ISO CPIO AR Only With Round-Trip
The system SHALL add `.iso`, `.cpio`, `.a`, `.ar`, and `.lib` as archive families only if 7zz (or an equivalent already-supported tool) can extract and write that family without changing container type. If write support is absent, these extensions SHALL stay unsupported.

#### Scenario: write supported
- **WHEN** 7zz can extract and create a CPIO archive
- **THEN** `.cpio` is walked like tar and rewritten as CPIO

#### Scenario: ISO write unsupported
- **WHEN** 7zz cannot write ISO
- **THEN** `.iso` is not registered as a supported archive
