# About

This tool and library were written to optimize Microsoft Word / Libreoffice ZIP based files, archives, and compressed files. It uses 7-Zip, jpegoptim, pngquant, Ghostscript (with qpdf fallback), gifsicle, dwebp/cwebp, svgo/scour, ImageMagick/tiffcp, ffmpeg, and optionally pigz to recompress not only host zip files but also all images, videos, PDFs, archives, and other suitable files inside them.

filerepack supports a wide variety of file formats including Office documents, archives (ZIP, 7z), compressed files (GZIP), images (JPEG, PNG, GIF, WebP, SVG, TIF, TIFF), videos (WMV, MP4, AVI, ASF), PDFs, and can optimize all nested files within archives.

## Installation

### Python Package Installation

At the command line:

```bash
pip install filerepack
```

Or, if you don't have pip installed:

```bash
easy_install filerepack
```

If you want to install from the latest sources, you can do:

```bash
git clone https://github.com/ivbeg/filerepack.git
cd filerepack
pip install -e .
```

### System Requirements

filerepack requires Python 3.3+ and the following command-line tools (see [Installing Required Command Line Tools](#installing-required-command-line-tools) section below):

**Core Requirements:**
- Python 3.3 or higher
- `zip` - Standard ZIP archiver
- `7zz` (7-Zip) - Advanced compression tool
- `jpegoptim` - JPEG optimization tool
- `pngquant` - PNG optimization tool

**Optional (for extended format support):**
- `gs` (Ghostscript) - PDF optimization (primary, recommended)
- `qpdf` - PDF optimization (fallback)
- `gifsicle` - GIF optimization
- `dwebp` and `cwebp` - WebP tools
- `svgo` or `scour` - SVG optimization
- `convert` (ImageMagick) or `magick` - TIF/TIFF optimization (primary, recommended)
- `tiffcp` - TIF/TIFF optimization (fallback)
- `ffmpeg` - Video processing
- `pigz` - Faster GZIP compression
- `duckdb` - Python package for Parquet compression (`pip install duckdb`)
- `unrar` - RAR archive extraction (preferred for RAR files, falls back to 7zz if not available)
- `rar` - RAR archive recompression (WinRAR command-line tool, optional - falls back to 7z if not available)


## Command line

filerepack provides two main commands:

### Repack a single file

```bash
filerepack repack <filename> [OPTIONS]
```

Repacks a single file (docx, xlsx, pptx, zip, 7z, gz, parquet, pdf, gif, webp, svg, wmv, mp4, avi, asf, etc.) and all images, videos, PDFs, nested archives, and compressed files inside it for better compression.

**Basic Options:**
- `--ultra`: Use ultra compression level for parquet files (slower but better compression)
- `--dryrun`: Calculate space savings without modifying files
- `--deep/--no-deep`: Look deeper into archive files like zip or 7z files (default: True)

**Verbosity Options:**
- `--quiet`: Quiet mode - minimal output (errors only)
- `--verbose`: Verbose mode - detailed output
- `--debug`: Debug mode - maximum verbosity

**Processing Control:**
- `--no-images`: Skip image optimization
- `--no-archives`: Skip nested archive processing

**Filtering Options:**
- `--min-savings <percent>`: Only process files if savings >= X% (e.g., `--min-savings 5.0`)
- `--min-size <size>`: Minimum file size to process (e.g., `--min-size 1MB`)
- `--max-size <size>`: Maximum file size to process (e.g., `--max-size 100MB`)

**Compression Options:**
- `--compression-level <1-9>`: Compression level (1=fast, 9=best, default: 9)
- `--jpeg-quality <1-100>`: JPEG quality (default: 85)
- `--png-quality <high|medium|low>`: PNG quality (default: high)
- `--wmv-lossless`: Use lossless compression for video files (WMV, MP4, AVI, ASF) - default is lossy high-quality

**Output Options:**
- `--backup`: Create backup before processing
- `--backup-dir <path>`: Directory for backups
- `--output-dir <path>`: Output directory for processed files
- `--json`: Output results in JSON format
- `--csv`: Output results in CSV format
- `--log-file <path>`: Write log to file
- `--stats`: Show detailed statistics

### Bulk repack multiple files

```bash
filerepack bulk <directory> [OPTIONS]
```

Recursively repacks all supported files in a directory. By default, `.zip` files are skipped (use `--no-skip-zip` to include them).

**Basic Options:**
- `--skip-zip/--no-skip-zip`: Skip or include `.zip` files (default: skip)
- `--ultra`: Use ultra compression level for parquet files (slower but better compression)
- `--dryrun`: Calculate space savings without modifying files
- `--deep/--no-deep`: Look deeper into archive files like zip or 7z files (default: True)

**Verbosity Options:**
- `--quiet`: Quiet mode - minimal output (errors only)
- `--verbose`: Verbose mode - detailed output
- `--debug`: Debug mode - maximum verbosity

**Processing Control:**
- `--no-images`: Skip image optimization
- `--no-archives`: Skip nested archive processing
- `--continue-on-error`: Continue processing after errors
- `--jobs <N>`: Number of parallel jobs (default: 1, note: currently processes sequentially)

**Filtering Options:**
- `--min-savings <percent>`: Only process files if savings >= X% (e.g., `--min-savings 5.0`)
- `--min-size <size>`: Minimum file size to process (e.g., `--min-size 1MB`)
- `--max-size <size>`: Maximum file size to process (e.g., `--max-size 100MB`)
- `--include-ext <exts>`: Comma-separated list of extensions to include (e.g., `--include-ext docx,xlsx,pptx`)
- `--exclude-ext <exts>`: Comma-separated list of extensions to exclude

**Compression Options:**
- `--compression-level <1-9>`: Compression level (1=fast, 9=best, default: 9)
- `--jpeg-quality <1-100>`: JPEG quality (default: 85)
- `--png-quality <high|medium|low>`: PNG quality (default: high)
- `--wmv-lossless`: Use lossless compression for video files (WMV, MP4, AVI, ASF) - default is lossy high-quality

**Output Options:**
- `--backup`: Create backup before processing
- `--backup-dir <path>`: Directory for backups
- `--output-dir <path>`: Output directory for processed files
- `--json`: Output results in JSON format
- `--csv`: Output results in CSV format
- `--log-file <path>`: Write log to file
- `--stats`: Show detailed statistics
- `--progress`: Show progress indicator
- `--progress-interval <N>`: Update progress every N files (default: 10)

**Size Format:** Size options (`--min-size`, `--max-size`) support human-readable formats:
- Bytes: `1000`, `1000B`
- Kilobytes: `1KB`, `1.5KB`
- Megabytes: `1MB`, `2.5MB`
- Gigabytes: `1GB`, `2GB`

## Examples

### Repack a single document

```bash
filerepack repack CP_CONTRACT_160166.docx
```

Recompresses `CP_CONTRACT_160166.docx` including all zip files, images and other suitable files inside it.

**Output example:**
```
File CP_CONTRACT_160166.docx shrinked 2456789 -> 1892345 (23.01%)
Files recompressed:
- word/media/image1.jpg: 456789 -> 345678 (24.35%)
- word/media/image2.png: 123456 -> 98765 (20.00%)
```

### Repack a presentation file

```bash
filerepack repack presentation.pptx
```

Optimizes PowerPoint presentation file and all embedded images.

### Repack a spreadsheet

```bash
filerepack repack data.xlsx
```

Compresses Excel spreadsheet file and embedded media.

### Repack all files in a directory

```bash
filerepack bulk ./documents
```

Recursively processes all supported files (docx, xlsx, pptx, etc.) in the `documents` directory and subdirectories.

**Output example:**
```
Scanning directory: ./documents
Processing: ./documents/file1.docx
  ✓ ./documents/file1.docx: 2456789 -> 1892345 (23.01%)
Processing: ./documents/subfolder/file2.pptx
  ✓ ./documents/subfolder/file2.pptx: 3456789 -> 2678901 (22.51%)

Summary:
  Files processed successfully: 2
  Files failed: 0
  Original total size: 5.64 MB
  Final total size: 4.36 MB
  Space saved: 1.28 MB (22.70%)
```

### Repack all files including ZIP archives

```bash
filerepack bulk ./archives --no-skip-zip
```

Processes all supported files including `.zip` files in the directory.

### Repack a GZIP compressed file

```bash
filerepack repack data.gz
```

Repacks a GZIP file with maximum compression. If `pigz` (parallel gzip) is available, it will be used for faster compression; otherwise, Python's built-in gzip module is used.

**Output example:**
```
File data.gz shrinked 1024000 -> 987654 (3.55%)
```

### Repack a PDF file

```bash
filerepack repack document.pdf
```

Optimizes a PDF file using Ghostscript (primary) or qpdf (fallback) for lossless compression. Ghostscript typically provides better compression ratios. The PDF structure is optimized for better compression while maintaining all content and functionality.

**Output example:**
```
File document.pdf shrinked 2456789 -> 2234567 (9.05%)
```

### Repack image files

```bash
# Compress a GIF file
filerepack repack animation.gif

# Compress a WebP file
filerepack repack image.webp

# Compress an SVG file
filerepack repack icon.svg

# Compress a TIF/TIFF file
filerepack repack image.tif
filerepack repack image.tiff
```

Optimizes GIF, WebP, SVG, and TIF/TIFF files using specialized tools:
- **GIF**: Uses `gifsicle` for lossless optimization
- **WebP**: Uses `dwebp` and `cwebp` for lossless recompression
- **SVG**: Uses `svgo` (preferred) or `scour` (fallback) for optimization
- **TIF/TIFF**: Uses ImageMagick (primary) or `tiffcp` (fallback) for lossless LZW compression

**Output example:**
```
File animation.gif shrinked 123456 -> 98765 (20.00%)
File image.webp shrinked 234567 -> 198765 (15.25%)
File icon.svg shrinked 45678 -> 34567 (24.35%)
File image.tif shrinked 345678 -> 267890 (22.50%)
```

### Repack video files

```bash
# Compress a WMV file (lossy, high quality - default)
filerepack repack video.wmv

# Compress a WMV file (lossless)
filerepack repack video.wmv --wmv-lossless

# Compress MP4, AVI, or ASF files
filerepack repack video.mp4
filerepack repack video.avi
filerepack repack video.asf

# Lossless compression for videos
filerepack repack video.mp4 --wmv-lossless
```

Compresses video files using FFmpeg with H.264 codec:
- **MP4**: Keeps MP4 container
- **WMV, AVI, ASF**: Converts to MP4 container (better compatibility)
- **Lossy mode** (default): High quality compression with CRF 18
- **Lossless mode**: True lossless compression with CRF 0 (larger files, slower)

**Note:** WMV, AVI, and ASF files will be converted to MP4 format after compression.

**Output example:**
```
File video.wmv shrinked 52428800 -> 45678901 (12.87%)
File video.mp4 shrinked 45678901 -> 42345678 (7.30%)
```

### Repack a 7z archive file

```bash
filerepack repack archive.7z
```

Repacks a 7z archive file with maximum compression, optimizing all nested files (images, archives, etc.) inside it.

**Output example:**
```
File archive.7z shrinked 5242880 -> 4567890 (12.87%)
Files recompressed:
- nested/file1.jpg: 123456 -> 98765 (20.00%)
- nested/subarchive.zip: 234567 -> 198765 (15.25%)
```

### Repack a RAR archive file

```bash
filerepack repack archive.rar
```

Repacks a RAR archive file with maximum compression, optimizing all nested files (images, archives, etc.) inside it. If the `rar` command-line tool (WinRAR) is not available, the file will be extracted, optimized, and recompressed as a 7z archive instead.

**Output example:**
```
File archive.rar shrinked 5242880 -> 4567890 (12.87%)
Files recompressed:
- nested/file1.jpg: 123456 -> 98765 (20.00%)
- nested/subarchive.zip: 234567 -> 198765 (15.25%)
```

**Note:** RAR recompression requires the `rar` command-line tool (from WinRAR). If not available, RAR files will be converted to 7z format after optimization.

### Preview compression results (dryrun mode)

```bash
filerepack repack large_file.docx --dryrun
```

Shows what the compression results would be without actually modifying the file.

**Output example:**
```
[DRYRUN] File large_file.docx would shrink 5242880 -> 4567890 (12.87%)
Files recompressed:
- word/media/image1.jpg: 123456 -> 98765 (20.00%)
```

### Use ultra compression for parquet files

```bash
filerepack repack data.parquet --ultra
```

Uses the highest compression level (22) for parquet files, which is slower but provides better compression than the default level (19).

### Bulk repack with dryrun to preview results

```bash
filerepack bulk ./documents --dryrun
```

Preview compression results for all files in a directory without modifying them.

**Output example:**
```
[DRYRUN MODE] Files will not be modified.
Scanning directory: ./documents
Processing: ./documents/file1.docx
  ✓ ./documents/file1.docx: 2456789 -> 1892345 (23.01%) [DRYRUN]
Processing: ./documents/file2.gz
  ✓ ./documents/file2.gz: 1024000 -> 987654 (3.55%) [DRYRUN]

Summary:
  Files processed successfully: 2
  Files failed: 0
  Original total size: 3.32 MB
  Final total size: 2.75 MB
  Space that would be saved: 0.57 MB (17.17%) [DRYRUN]
```

### Control verbosity

```bash
# Quiet mode - minimal output
filerepack repack document.docx --quiet

# Verbose mode - detailed output
filerepack repack document.docx --verbose

# Debug mode - maximum verbosity
filerepack repack document.docx --debug
```

### Skip image or archive processing

```bash
# Skip image optimization (faster processing)
filerepack repack document.docx --no-images

# Skip nested archive processing
filerepack repack archive.zip --no-archives

# Skip both for maximum speed
filerepack bulk ./documents --no-images --no-archives
```

### Filter files by size

```bash
# Only process files larger than 1MB
filerepack bulk ./documents --min-size 1MB

# Only process files smaller than 100MB
filerepack bulk ./documents --max-size 100MB

# Process files between 1MB and 100MB
filerepack bulk ./documents --min-size 1MB --max-size 100MB
```

### Filter by extension

```bash
# Only process Office documents
filerepack bulk ./documents --include-ext docx,xlsx,pptx

# Process all except ZIP files
filerepack bulk ./documents --exclude-ext zip,7z
```

### Minimum savings threshold

```bash
# Only process files with at least 5% savings
filerepack bulk ./documents --min-savings 5.0

# Skip files with minimal compression benefit
filerepack bulk ./documents --min-savings 10.0
```

### Create backups

```bash
# Create backup before processing
filerepack repack important.docx --backup

# Create backups in specific directory
filerepack bulk ./documents --backup --backup-dir ./backups
```

### Custom compression levels

```bash
# Fast compression (level 1)
filerepack repack archive.zip --compression-level 1

# Maximum compression (level 9, default)
filerepack repack archive.zip --compression-level 9

# Balance between speed and compression
filerepack bulk ./documents --compression-level 5
```

### Image quality settings

```bash
# High JPEG quality (less compression, better quality)
filerepack repack document.docx --jpeg-quality 95

# Lower JPEG quality (more compression, smaller files)
filerepack repack document.docx --jpeg-quality 70

# PNG quality settings
filerepack repack document.docx --png-quality high    # Best quality (slower)
filerepack repack document.docx --png-quality medium  # Balanced
filerepack repack document.docx --png-quality low     # Fastest

# Video compression settings
filerepack repack video.mp4                    # Lossy high-quality (default)
filerepack repack video.wmv --wmv-lossless    # Lossless compression
```

### Output to different directory

```bash
# Process files and save to output directory
filerepack bulk ./documents --output-dir ./compressed

# Non-destructive processing (original files preserved)
filerepack repack document.docx --output-dir ./compressed --backup
```

### JSON and CSV output

```bash
# Output results in JSON format
filerepack bulk ./documents --json > results.json

# Output results in CSV format
filerepack bulk ./documents --csv > results.csv

# Process single file with JSON output
filerepack repack document.docx --json > result.json
```

### Logging

```bash
# Write detailed log to file
filerepack bulk ./documents --log-file processing.log

# Combine with verbose mode for maximum detail
filerepack bulk ./documents --verbose --log-file processing.log
```

### Progress reporting

```bash
# Show progress indicator
filerepack bulk ./documents --progress

# Update progress every 5 files
filerepack bulk ./documents --progress --progress-interval 5
```

### Detailed statistics

```bash
# Show detailed statistics
filerepack repack document.docx --stats

# Combine with bulk processing
filerepack bulk ./documents --stats --verbose
```

**Output example with stats:**
```
File document.docx shrinked 2456789 -> 1892345 (23.01%)
Files recompressed:
- word/media/image1.jpg: 456789 -> 345678 (24.35%)

Statistics:
  Processing time: 2.34s
  Files processed: 1
```

### Continue on error

```bash
# Continue processing even if some files fail
filerepack bulk ./documents --continue-on-error

# Useful for batch processing with some corrupted files
filerepack bulk ./documents --continue-on-error --verbose
```

### Combined example: Advanced bulk processing

```bash
filerepack bulk ./documents \
  --min-size 1MB \
  --max-size 100MB \
  --min-savings 5.0 \
  --include-ext docx,xlsx,pptx,mp4,pdf \
  --compression-level 7 \
  --jpeg-quality 85 \
  --wmv-lossless \
  --backup \
  --backup-dir ./backups \
  --output-dir ./compressed \
  --progress \
  --stats \
  --log-file processing.log \
  --json > results.json
```

This command:
- Processes only Office documents, MP4 videos, and PDFs between 1MB and 100MB
- Only processes files with at least 5% savings
- Uses compression level 7
- Sets JPEG quality to 85
- Uses lossless compression for video files
- Creates backups in ./backups
- Saves processed files to ./compressed
- Shows progress indicator
- Displays detailed statistics
- Logs to processing.log
- Outputs results in JSON format

### Supported file formats

filerepack supports the following file formats:

- **Microsoft Office**: docx, xlsx, pptx, docm, xlsm, pptm, and other OOXML formats
- **LibreOffice/OpenOffice**: odt, ods, odp, ott, otp
- **Apple iWork**: pages, key, numbers
- **Online Services**: rtb (Miro board files)
- **Archives**: zip, 7z, rar, jar, egg, whl, apk, ipa
- **Compressed files**: gz (GZIP), xz, bz2
- **Data files**: parquet
- **EBooks**: epub, fb2, lpf
- **PDF files**: pdf (lossless optimization)
- **Image formats**: jpg, jpeg, png, gif, webp, svg, tif, tiff
- **Video formats**: wmv, mp4, avi, asf (with lossless or lossy compression)
- **Other**: xmind, vsdx, kmz, 3mf, cbz, mxl, and more

**Notes:**
- GZIP files use `pigz` (parallel gzip) if available for faster compression, otherwise fall back to Python's built-in gzip module.
- PDF files use Ghostscript (primary) for better compression, with qpdf as fallback if Ghostscript is not available.
- TIF/TIFF files use ImageMagick (primary) for better compression, with tiffcp as fallback if ImageMagick is not available.
- Video files (WMV, AVI, ASF) are converted to MP4 container format for better compatibility.
- Video compression defaults to lossy high-quality mode; use `--wmv-lossless` for true lossless compression.
- Parquet files require the `duckdb` Python package (install via `pip install duckdb`).
- RAR files use `unrar` for extraction (preferred, falls back to `7zz` if not available). For recompression, RAR files require the `rar` command-line tool (from WinRAR). If `rar` is not available, RAR files will be extracted, optimized, and recompressed as 7z format instead.


## Code Examples

### Repack a presentation file

```python
>>> from filerepack import FileRepacker
>>> rp = FileRepacker()
>>> stats = rp.repack_zip_file(filename="some_presentation.pptx")
>>> print(f"Compressed: {stats['final'][0]} -> {stats['final'][1]} ({stats['final'][2]:.2f}%)")
```

### Repack with options

```python
>>> from filerepack import FileRepacker
>>> rp = FileRepacker()
>>> options = {
...     'debug': True,
...     'ultra': True,  # Use ultra compression for parquet files
...     'dryrun': False,
...     'quiet': False,
...     'deep_walking': True,  # Process nested archives
...     'pack_images': True,  # Optimize images
...     'pack_archives': True,  # Process nested archives
...     'compression_level': 9,  # Maximum compression
...     'jpeg_quality': 85,  # JPEG quality
...     'png_quality': 'high',  # PNG quality
...     'wmv_lossless': False  # Video compression mode (False = lossy, True = lossless)
... }
>>> stats = rp.repack_zip_file(filename="data.parquet", def_options=options)
```

### Repack video files programmatically

```python
>>> from filerepack.repack import pack_mp4, pack_wmv
>>> # Lossy compression (default)
>>> result = pack_mp4("video.mp4", debug=True, quiet=False, lossless=False)
>>> if result:
...     print(f"Compressed: {result[1]} -> {result[2]} ({result[3]:.2f}%)")
>>> # Lossless compression
>>> result = pack_wmv("video.wmv", debug=True, quiet=False, lossless=True)
>>> if result:
...     print(f"Compressed: {result[1]} -> {result[2]} ({result[3]:.2f}%)")
```

### Repack PDF and image files programmatically

```python
>>> from filerepack.repack import pack_pdf, pack_gif, pack_webp, pack_svg, pack_tif
>>> # PDF compression
>>> result = pack_pdf("document.pdf", debug=True, quiet=False)
>>> # GIF compression
>>> result = pack_gif("animation.gif", debug=True, quiet=False)
>>> # WebP compression
>>> result = pack_webp("image.webp", debug=True, quiet=False)
>>> # SVG compression
>>> result = pack_svg("icon.svg", debug=True, quiet=False)
>>> # TIF/TIFF compression
>>> result = pack_tif("image.tif", debug=True, quiet=False)
```

### Recursively repack all images

```python
>>> from filerepack import FileRepacker
>>> rp = FileRepacker()
>>> stats = rp.pack_images('some_media_path', recursive=True)
>>> print(f"Processed {stats['stats'][0]} files")
>>> print(f"Total size: {stats['stats'][1]} -> {stats['stats'][2]}")
```

### Repack a GZIP file programmatically

```python
>>> from filerepack.repack import pack_gzip
>>> result = pack_gzip("data.gz", debug=True, quiet=False)
>>> if result:
...     print(f"Compressed: {result[1]} -> {result[2]} ({result[3]:.2f}%)")
```

### Repack a 7z archive

```python
>>> from filerepack import FileRepacker
>>> rp = FileRepacker()
>>> stats = rp.repack_zip_file("archive.7z")
>>> print(f"Final size: {stats['final'][1]} bytes")
>>> print(f"Compression ratio: {stats['final'][2]:.2f}%")
```



## Requirements

filerepack works in both Windows, Linux, and macOS environments.

**Required tools:**
- `zip` - Standard ZIP archiver
- `7zz` (7-Zip) - Advanced compression tool
- `jpegoptim` - JPEG optimization tool
- `pngquant` - PNG optimization tool

**Optional tools (for additional format support):**
- `pigz` - Parallel gzip implementation (faster GZIP compression, automatically detected if available)
- `gs` (Ghostscript) - PDF optimization (primary tool for PDF compression, provides better compression than qpdf)
- `qpdf` - PDF optimization (fallback tool for PDF compression if Ghostscript is not available)
- `unrar` - RAR archive extraction (preferred for RAR files, falls back to 7zz if not available)
- `rar` - RAR archive recompression (WinRAR command-line tool, optional - falls back to 7z if not available)
- `gifsicle` - GIF optimization (required for GIF compression)
- `dwebp` and `cwebp` - WebP tools (required for WebP compression)
- `svgo` or `scour` - SVG optimization (required for SVG compression)
- `convert` (ImageMagick) or `magick` - TIF/TIFF optimization (primary tool, provides better compression)
- `tiffcp` - TIF/TIFF optimization (fallback tool if ImageMagick is not available)
- `ffmpeg` - Video processing (required for video file compression: WMV, MP4, AVI, ASF)
- `duckdb` - Parquet file compression (optional Python package, install via `pip install duckdb`)

## Installing Required Command Line Tools

Before using filerepack, you need to install the following command line tools on your system:

**Core tools (required):**
- `zip` - Standard ZIP archiver
- `7zz` (7-Zip) - Advanced compression tool
- `jpegoptim` - JPEG optimization tool
- `pngquant` - PNG optimization tool

**Additional tools (for extended format support):**
- `gs` (Ghostscript) - PDF optimization (primary, provides better compression)
- `qpdf` - PDF optimization (fallback if Ghostscript is not available)
- `gifsicle` - GIF optimization
- `webp` - WebP tools (includes dwebp and cwebp)
- `svgo` or `scour` - SVG optimization
- `imagemagick` - TIF/TIFF optimization (primary, provides better compression)
- `libtiff` - TIF/TIFF optimization (fallback, includes tiffcp)
- `ffmpeg` - Video processing
- `duckdb` - Parquet file compression (Python package: `pip install duckdb`)

### macOS

Using [Homebrew](https://brew.sh/) (recommended):

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install core required tools
brew install zip
brew install p7zip
brew install jpegoptim
brew install pngquant

# Optional: Install pigz for faster GZIP compression
brew install pigz

# Optional: Install tools for additional format support
brew install ghostscript   # PDF optimization (primary, better compression)
brew install qpdf          # PDF optimization (fallback)
brew install gifsicle      # GIF optimization
brew install webp          # WebP tools (includes dwebp and cwebp)
brew install imagemagick   # TIF/TIFF optimization (primary, better compression)
brew install libtiff       # TIF/TIFF optimization (fallback, includes tiffcp)
brew install ffmpeg        # Video processing

# For SVG optimization, install via npm or pip
npm install -g svgo        # Preferred SVG optimizer
# OR
pip install scour          # Alternative SVG optimizer

# For Parquet file compression
pip install duckdb          # Python package for Parquet compression

# Optional: Install unrar for RAR archive extraction (preferred, falls back to 7zz if not available)
brew install unrar          # RAR extraction tool
```

Alternatively, using [MacPorts](https://www.macports.org/):

```bash
sudo port install zip
sudo port install p7zip
sudo port install jpegoptim
sudo port install pngquant
```

**Note:** After installation, ensure `7zz` is available. If `p7zip` installs it as `7z`, you may need to create a symlink:
```bash
sudo ln -s /usr/local/bin/7z /usr/local/bin/7zz
```

### Ubuntu / Debian

Using `apt` package manager:

```bash
sudo apt-get update
sudo apt-get install zip p7zip-full jpegoptim pngquant

# Optional: Install pigz for faster GZIP compression
sudo apt-get install pigz

# Optional: Install tools for additional format support
sudo apt-get install ghostscript qpdf gifsicle webp imagemagick libtiff-tools ffmpeg unrar

# For SVG optimization, install via npm or pip
sudo npm install -g svgo   # Preferred SVG optimizer
# OR
sudo apt-get install python3-scour  # Alternative SVG optimizer

# For Parquet file compression
pip install duckdb          # Python package for Parquet compression

# Optional: Install unrar for RAR archive extraction (preferred, falls back to 7zz if not available)
brew install unrar          # RAR extraction tool
```

**Note:** After installation, ensure `7zz` is available. If `p7zip-full` installs it as `7z`, you may need to create a symlink:
```bash
sudo ln -s /usr/bin/7z /usr/bin/7zz
```

### Windows

#### Option 1: Using Chocolatey (recommended)

1. Install [Chocolatey](https://chocolatey.org/install) if you don't have it
2. Open PowerShell as Administrator and run:

```powershell
# Core tools
choco install zip 7zip jpegoptim pngquant -y

# Optional: Additional format support
choco install ghostscript qpdf gifsicle webp imagemagick libtiff ffmpeg -y

# For SVG optimization, install via npm
npm install -g svgo
# OR install Python and use pip
pip install scour

# For Parquet file compression
pip install duckdb
```

#### Option 2: Manual Installation

1. **zip**: Usually pre-installed on Windows. If not, install from [Info-ZIP](http://www.info-zip.org/Zip.html) or use the built-in Windows compression.

2. **7-Zip**: 
   - Download from [7-Zip official website](https://www.7-zip.org/)
   - Install and add `C:\Program Files\7-Zip` to your system PATH
   - Rename `7z.exe` to `7zz.exe` in the installation directory, or create a symlink

3. **jpegoptim**:
   - Download from [jpegoptim releases](https://github.com/tjko/jpegoptim/releases) or use [Cygwin](https://www.cygwin.com/)
   - Add the installation directory to your system PATH

4. **pngquant**:
   - Download Windows binaries from [pngquant.org](https://pngquant.org/)
   - Extract and add the directory to your system PATH

5. **Ghostscript** (for PDF compression, primary tool):
   - Download from [Ghostscript website](https://www.ghostscript.com/download/gsdnld.html)
   - Install and add the `bin` directory to your system PATH
   - On Windows, the executable is typically `gswin64c.exe` or `gswin32c.exe`

6. **qpdf** (for PDF compression, fallback if Ghostscript is not available):
   - Download from [qpdf website](https://qpdf.sourceforge.io/)
   - Extract and add the directory to your system PATH

7. **ImageMagick** (for TIF/TIFF compression, primary tool):
   - Download from [ImageMagick website](https://imagemagick.org/script/download.php)
   - Install and add the installation directory to your system PATH
   - On Windows, the executable is typically `convert.exe` or `magick.exe`

8. **libtiff** (for TIF/TIFF compression, fallback):
   - Download from [libtiff website](https://www.libtiff.org/download.html)
   - Extract and add the directory to your system PATH
   - Includes `tiffcp` tool

9. **gifsicle** (for GIF compression):
   - Download from [gifsicle website](https://www.lcdf.org/gifsicle/)
   - Extract and add the directory to your system PATH

10. **WebP tools** (for WebP compression):
   - Download from [WebP website](https://developers.google.com/speed/webp/download)
   - Extract and add the directory to your system PATH

11. **FFmpeg** (for video compression):
   - Download from [FFmpeg website](https://ffmpeg.org/download.html)
   - Extract and add the `bin` directory to your system PATH

12. **svgo** (for SVG compression, preferred):
   - Install Node.js from [nodejs.org](https://nodejs.org/)
   - Run: `npm install -g svgo`

13. **scour** (alternative SVG optimizer):
    - Install Python from [python.org](https://www.python.org/)
    - Run: `pip install scour`

14. **duckdb** (for Parquet file compression):
    - Install Python from [python.org](https://www.python.org/)
    - Run: `pip install duckdb`

15. **unrar** (for RAR archive extraction, optional but recommended):
    - Download from [RARLab website](https://www.rarlab.com/rar_add.htm) or use package manager
    - On Windows: Download UnRAR from [RARLab](https://www.rarlab.com/rar_add.htm) and add to PATH
    - On macOS: `brew install unrar`
    - On Linux: `sudo apt-get install unrar` or `sudo yum install unrar`
    - **Note:** If `unrar` is not available, filerepack will fall back to using `7zz` for RAR extraction

16. **rar** (for RAR archive recompression, optional):
    - Download WinRAR from [WinRAR website](https://www.winrar.com/)
    - Install and add the installation directory to your system PATH
    - The command-line tool `rar.exe` is included with WinRAR
    - **Note:** If `rar` is not available, RAR files will be extracted, optimized, and recompressed as 7z format instead

#### Adding to PATH on Windows

1. Right-click "This PC" → Properties → Advanced system settings
2. Click "Environment Variables"
3. Under "System variables", find and select "Path", then click "Edit"
4. Click "New" and add the directory containing each tool
5. Click "OK" to save

After installation, verify all tools are accessible by running:
```bash
# Core tools
zip --version
7zz
jpegoptim --version
pngquant --version

# Optional tools
pigz --version          # Faster GZIP compression
gs --version            # PDF optimization (primary, Ghostscript)
qpdf --version          # PDF optimization (fallback)
gifsicle --version      # GIF optimization
dwebp -version          # WebP tools
cwebp -version          # WebP tools
svgo --version          # SVG optimization (or scour --version)
convert --version       # TIF/TIFF optimization (primary, ImageMagick)
tiffcp                  # TIF/TIFF optimization (fallback)
ffmpeg -version         # Video processing
python -c "import duckdb; print(duckdb.__version__)"  # Parquet compression
unrar                   # RAR archive extraction (optional, falls back to 7zz if not available)
rar                     # RAR archive recompression (optional, falls back to 7z if not available)
```

## Features

- **Multi-format support**: Handles Office documents, archives (ZIP, 7z, RAR), compressed files (GZIP, XZ, BZ2), data files (Parquet), PDFs, images (JPEG, PNG, GIF, WebP, SVG, TIF, TIFF), and videos (WMV, MP4, AVI, ASF)
- **Nested optimization**: Recursively optimizes images, videos, PDFs, archives, and compressed files within archives
- **Smart compression**: Uses maximum compression levels for all supported formats
- **Video compression**: Supports both lossless and lossy high-quality compression for video files
- **Image optimization**: Lossless optimization for GIF, WebP, SVG, and TIF/TIFF; lossy optimization for JPEG and PNG
- **PDF optimization**: Lossless PDF structure optimization using Ghostscript (primary) or qpdf (fallback)
- **Parallel processing**: Automatically uses `pigz` for faster GZIP compression when available
- **Dry-run mode**: Preview compression results without modifying files
- **Ultra compression**: Optional ultra compression mode for Parquet files
- **Cross-platform**: Works on Windows, Linux, and macOS
- **Flexible filtering**: Filter files by size, extension, and minimum savings threshold
- **Verbosity control**: Quiet, normal, verbose, and debug output modes
- **Backup support**: Automatic backup creation before processing
- **Output formats**: JSON and CSV output for programmatic processing
- **Progress reporting**: Real-time progress indicators for long operations
- **Error handling**: Continue processing after errors in bulk mode
- **Customizable compression**: Adjustable compression levels, image quality settings, and video compression modes
- **Logging**: Detailed logging to files for audit trails
- **Statistics**: Comprehensive statistics and performance metrics


## Acknowledgements

