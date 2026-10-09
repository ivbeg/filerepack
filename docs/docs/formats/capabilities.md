---
title: Format capability registry
---

Generated from `filerepack.format_registry` and the typed capability adapters.

Registered writers still require their declared tools, Python extras and 
preservation validators. Protected or unsupported content is refused. 
Use `filerepack doctor --json` for availability on the current machine. 
An inspection-only entry has no registered compression writer.
Registered describes routing. Successful backend create/read qualification 
requires its recorded profile evidence; complete runtime writer probing remains open.

| Extension | Family | Adapter | Writer | Validator | Tools | Extra |
| --- | --- | --- | --- | --- | --- | --- |
| `3gp` | standalone | 3gp | registered | yes | ffmpeg, ffprobe | — |
| `3mf` | zip | 3mf | registered | yes | szip | — |
| `7z` | 7z | 7z | registered | yes | szip | — |
| `aab` | zip | aab | registered | yes | szip | — |
| `aar` | zip | aar | registered | yes | szip | — |
| `accdt` | zip | accdt | registered | yes | szip | — |
| `afdesign` | zip | afdesign | registered | yes | szip | — |
| `afphoto` | zip | afphoto | registered | yes | szip | — |
| `afpub` | zip | afpub | registered | yes | szip | — |
| `ai` | standalone | ai | registered | yes | Python | — |
| `air` | zip | air | registered | yes | szip | — |
| `ape` | standalone | ape | registered | yes | Python | — |
| `apk` | zip | apk | registered | yes | szip | — |
| `apks` | zip | apks | registered | yes | szip | — |
| `apng` | standalone | png | registered | yes | oxipng, optipng | validation |
| `appx` | zip | appx | registered | yes | szip | — |
| `appxbundle` | zip | appxbundle | registered | yes | szip | — |
| `arrow` | standalone | arrow | registered | yes | Python | data |
| `ase` | standalone | aseprite | registered | yes | Python | validation |
| `aseprite` | standalone | aseprite | registered | yes | Python | validation |
| `asf` | standalone | asf | registered | yes | ffmpeg, ffprobe | — |
| `atom` | standalone | xml | registered | yes | Python | — |
| `avi` | standalone | avi | registered | yes | ffmpeg, ffprobe | — |
| `avif` | standalone | avif | registered | yes | avifdec, avifenc | validation |
| `avro` | standalone | avro | registered | yes | Python | data |
| `blend` | standalone | blend | registered | yes | Python | — |
| `bmp` | standalone | bmp | registered | yes | Python | validation |
| `br` | standalone | br | registered | yes | Python | — |
| `bz2` | standalone | bz2 | registered | yes | Python | — |
| `cab` | cab | cab | none | yes | szip | — |
| `car` | standalone | car | registered | yes | Python | — |
| `cb7` | 7z | cb7 | registered | yes | szip | — |
| `cbr` | rar | cbr | registered | yes | szip | — |
| `cbt` | tar | cbt | registered | yes | szip | — |
| `cbz` | zip | cbz | registered | yes | szip | — |
| `cpbz2` | cpio.bz2 | cpbz2 | registered | none | szip | — |
| `cpio` | cpio | cpio | registered | yes | szip | — |
| `cpio.bz2` | cpio.bz2 | cpio.bz2 | registered | none | szip | — |
| `crate` | tar.gz | crate | registered | yes | szip | — |
| `crtx` | zip | crtx | registered | yes | szip | — |
| `crx` | zip | crx | registered | yes | szip | — |
| `cur` | standalone | ico | registered | yes | Python | validation |
| `dae` | standalone | xml | registered | yes | Python | — |
| `db` | standalone | sqlite | registered | yes | Python | — |
| `dcm` | standalone | dcm | registered | none | Python | validation |
| `dcx` | standalone | pcx | registered | yes | Python | validation |
| `dib` | standalone | bmp | registered | yes | Python | validation |
| `dic` | standalone | dcm | registered | none | Python | validation |
| `dicom` | standalone | dcm | registered | none | Python | validation |
| `dng` | standalone | dng | registered | yes | Python | validation |
| `doc` | standalone | ole | registered | yes | Python | ole |
| `docm` | zip | docm | registered | yes | szip | — |
| `docx` | zip | docx | registered | yes | szip | — |
| `dot` | standalone | ole | registered | yes | Python | ole |
| `dotm` | zip | dotm | registered | yes | szip | — |
| `dotx` | zip | dotx | registered | yes | szip | — |
| `duckdb` | standalone | duckdb | registered | yes | Python | — |
| `dwfx` | zip | dwfx | registered | yes | szip | — |
| `ear` | zip | ear | registered | yes | szip | — |
| `egg` | zip | egg | registered | yes | szip | — |
| `epub` | zip | epub | registered | yes | szip | — |
| `exr` | standalone | exr | registered | yes | Python | validation |
| `fb2` | standalone | xml | registered | yes | Python | — |
| `fcstd` | zip | fcstd | registered | yes | szip | — |
| `feather` | standalone | feather | registered | yes | Python | data |
| `fit` | standalone | fits | registered | yes | Python | — |
| `fits` | standalone | fits | registered | yes | Python | — |
| `flac` | standalone | flac | registered | yes | flac | — |
| `fts` | standalone | fits | registered | yes | Python | — |
| `gcsx` | zip | gcsx | registered | yes | szip | — |
| `gem` | tar | gem | registered | yes | szip | — |
| `geojson` | standalone | json | registered | yes | Python | — |
| `gguf` | standalone | gguf | inspection only | none | Python | — |
| `gif` | standalone | gif | registered | yes | gifsicle | validation |
| `glox` | zip | glox | registered | yes | szip | — |
| `gltf` | standalone | json | registered | yes | Python | — |
| `gpkg` | standalone | gpkg | registered | none | Python | — |
| `gpx` | standalone | xml | registered | yes | Python | — |
| `gqsx` | zip | gqsx | registered | yes | szip | — |
| `gz` | standalone | gz | registered | yes | Python | — |
| `gzip` | standalone | gz | registered | yes | Python | — |
| `h5` | standalone | h5 | registered | yes | Python | scientific |
| `har` | standalone | json | registered | yes | Python | — |
| `hdf` | standalone | hdf | registered | none | Python | scientific |
| `hdf5` | standalone | hdf5 | registered | yes | Python | scientific |
| `heic` | standalone | heic | registered | yes | Python | validation |
| `heif` | standalone | heif | registered | yes | Python | validation |
| `hwp` | standalone | ole | registered | yes | Python | ole |
| `ibooks` | zip | ibooks | registered | yes | szip | — |
| `icns` | standalone | icns | registered | yes | Python | validation |
| `ico` | standalone | ico | registered | yes | Python | validation |
| `idml` | zip | idml | registered | yes | szip | — |
| `ifczip` | zip | ifczip | registered | yes | szip | — |
| `ipa` | zip | ipa | registered | yes | szip | — |
| `ipc` | standalone | ipc | registered | yes | Python | data |
| `ipsw` | zip | ipsw | registered | yes | szip | — |
| `ipynb` | standalone | json | registered | yes | Python | — |
| `j2k` | standalone | j2k | registered | yes | Python | validation |
| `jar` | zip | jar | registered | yes | szip | — |
| `jfi` | standalone | jpg | registered | yes | jpegtran | validation |
| `jfif` | standalone | jpg | registered | yes | jpegtran | validation |
| `jif` | standalone | jpg | registered | yes | jpegtran | validation |
| `jp2` | standalone | jp2 | registered | yes | Python | validation |
| `jpe` | standalone | jpg | registered | yes | jpegtran | validation |
| `jpeg` | standalone | jpg | registered | yes | jpegtran | validation |
| `jpf` | standalone | jpf | registered | yes | Python | validation |
| `jpg` | standalone | jpg | registered | yes | jpegtran | validation |
| `jpx` | standalone | jpx | registered | yes | Python | validation |
| `json` | standalone | json | registered | yes | Python | — |
| `jsonl` | standalone | jsonl | registered | yes | Python | — |
| `jxl` | standalone | jxl | registered | yes | djxl, cjxl | validation |
| `key` | zip | key | registered | yes | szip | — |
| `kml` | standalone | xml | registered | yes | Python | — |
| `kmz` | zip | kmz | registered | yes | szip | — |
| `kra` | zip | kra | registered | yes | szip | — |
| `kth` | zip | kth | registered | yes | szip | — |
| `lpf` | zip | lpf | registered | yes | szip | — |
| `lz` | standalone | lz | registered | yes | Python | — |
| `lz4` | standalone | lz4 | registered | yes | Python | — |
| `lzma` | standalone | lzma | registered | yes | Python | — |
| `lzo` | standalone | lzo | registered | yes | Python | — |
| `m2ts` | standalone | m2ts | registered | yes | ffmpeg, ffprobe | — |
| `m4a` | standalone | m4a | registered | yes | Python | — |
| `m4b` | standalone | m4a | registered | yes | Python | — |
| `m4v` | standalone | m4v | registered | yes | ffmpeg, ffprobe | — |
| `map` | standalone | json | registered | yes | Python | — |
| `mat` | standalone | mat | experimental | yes | Python | scientific |
| `mbtiles` | standalone | mbtiles | registered | none | Python | — |
| `mcaddon` | zip | mcaddon | registered | yes | szip | — |
| `mcpack` | zip | mcpack | registered | yes | szip | — |
| `mcworld` | zip | mcworld | registered | yes | szip | — |
| `mellel` | zip | mellel | registered | yes | szip | — |
| `mkv` | standalone | mkv | registered | yes | ffmpeg, ffprobe | — |
| `mov` | standalone | mov | registered | yes | ffmpeg, ffprobe | — |
| `mp3` | standalone | mp3 | registered | yes | mp3packer | — |
| `mp4` | standalone | mp4 | registered | yes | ffmpeg, ffprobe | — |
| `mpp` | standalone | ole | registered | yes | Python | ole |
| `msg` | standalone | ole | registered | yes | Python | ole |
| `msi` | standalone | ole | registered | yes | Python | ole |
| `msix` | zip | msix | registered | yes | szip | — |
| `mts` | standalone | mts | registered | yes | ffmpeg, ffprobe | — |
| `mxl` | zip | mxl | registered | yes | szip | — |
| `nbk` | zip | nbk | registered | yes | szip | — |
| `nc` | standalone | nc | registered | yes | Python | scientific |
| `nc4` | standalone | nc4 | registered | yes | Python | scientific |
| `ndjson` | standalone | jsonl | registered | yes | Python | — |
| `nib` | standalone | nib | registered | yes | Python | — |
| `nmbtemplate` | zip | nmbtemplate | registered | yes | szip | — |
| `notebook` | zip | notebook | registered | yes | szip | — |
| `npz` | zip | npz | registered | yes | szip | — |
| `nrrd` | standalone | nrrd | registered | yes | Python | — |
| `numbers` | zip | numbers | registered | yes | szip | — |
| `nupkg` | zip | nupkg | registered | yes | szip | — |
| `odb` | zip | odb | registered | yes | szip | — |
| `odc` | zip | odc | registered | yes | szip | — |
| `odf` | zip | odf | registered | yes | szip | — |
| `odg` | zip | odg | registered | yes | szip | — |
| `odi` | zip | odi | registered | yes | szip | — |
| `odm` | zip | odm | registered | yes | szip | — |
| `odp` | zip | odp | registered | yes | szip | — |
| `ods` | zip | ods | registered | yes | szip | — |
| `odt` | zip | odt | registered | yes | szip | — |
| `oex` | zip | oex | registered | yes | szip | — |
| `oga` | standalone | oga | registered | yes | Python | — |
| `ogg` | standalone | ogg | registered | yes | Python | — |
| `onepkg` | zip | onepkg | registered | yes | szip | — |
| `onnx` | standalone | onnx | inspection only | none | Python | — |
| `opus` | standalone | ogg | registered | yes | Python | — |
| `ora` | zip | ora | registered | yes | szip | — |
| `orc` | standalone | orc | registered | yes | Python | data |
| `osk` | zip | osk | registered | yes | szip | — |
| `otc` | zip | otc | registered | yes | szip | — |
| `otg` | zip | otg | registered | yes | szip | — |
| `oth` | zip | oth | registered | yes | szip | — |
| `oti` | zip | oti | registered | yes | szip | — |
| `otm` | zip | otm | registered | yes | szip | — |
| `otp` | zip | otp | registered | yes | szip | — |
| `ots` | zip | ots | registered | yes | szip | — |
| `ott` | zip | ott | registered | yes | szip | — |
| `oxps` | zip | oxps | registered | yes | szip | — |
| `oxt` | zip | oxt | registered | yes | szip | — |
| `pages` | zip | pages | registered | yes | szip | — |
| `parquet` | standalone | parquet | registered | yes | Python | data |
| `pbm` | standalone | pnm | registered | yes | Python | validation |
| `pcx` | standalone | pcx | registered | yes | Python | validation |
| `pdf` | standalone | pdf | registered | yes | Python | pdf |
| `pgm` | standalone | pnm | registered | yes | Python | validation |
| `pk3` | zip | pk3 | registered | yes | szip | — |
| `png` | standalone | png | registered | yes | oxipng, optipng | validation |
| `pnm` | standalone | pnm | registered | yes | Python | validation |
| `pot` | standalone | ole | registered | yes | Python | ole |
| `potm` | zip | potm | registered | yes | szip | — |
| `potx` | zip | potx | registered | yes | szip | — |
| `ppam` | zip | ppam | registered | yes | szip | — |
| `ppm` | standalone | pnm | registered | yes | Python | validation |
| `pps` | standalone | ole | registered | yes | Python | ole |
| `ppsm` | zip | ppsm | registered | yes | szip | — |
| `ppsx` | zip | ppsx | registered | yes | szip | — |
| `ppt` | standalone | ole | registered | yes | Python | ole |
| `pptm` | zip | pptm | registered | yes | szip | — |
| `pptx` | zip | pptx | registered | yes | szip | — |
| `psb` | standalone | psb | registered | yes | Python | validation |
| `psd` | standalone | psd | registered | yes | Python | validation |
| `pt` | standalone | checkpoint | registered | yes | Python | serialization |
| `pth` | standalone | checkpoint | registered | yes | Python | serialization |
| `pub` | standalone | ole | registered | yes | Python | ole |
| `puz` | zip | puz | registered | yes | szip | — |
| `qgd` | standalone | qgd | registered | yes | Python | — |
| `qgs` | standalone | qgs | registered | yes | Python | — |
| `qgz` | zip | qgz | registered | yes | szip | — |
| `rar` | rar | rar | registered | yes | szip | — |
| `rda` | standalone | r-serialization | registered | yes | Python | serialization |
| `rdata` | standalone | r-serialization | registered | yes | Python | serialization |
| `rds` | standalone | r-serialization | registered | yes | Python | serialization |
| `rels` | standalone | xml | registered | yes | Python | — |
| `rmskin` | zip | rmskin | registered | yes | szip | — |
| `rss` | standalone | xml | registered | yes | Python | — |
| `rtb` | zip | rtb | registered | yes | szip | — |
| `safetensors` | standalone | safetensors | inspection only | none | Python | — |
| `sav` | standalone | spss | experimental | yes | Python | scientific |
| `scrivx` | zip | scrivx | registered | yes | szip | — |
| `sketch` | zip | sketch | registered | yes | szip | — |
| `sldm` | zip | sldm | registered | yes | szip | — |
| `sldx` | zip | sldx | registered | yes | szip | — |
| `snupkg` | zip | snupkg | registered | yes | szip | — |
| `sqlite` | standalone | sqlite | registered | yes | Python | — |
| `sqlite3` | standalone | sqlite3 | registered | none | Python | — |
| `sqlitedb` | standalone | sqlite | registered | yes | Python | — |
| `stc` | zip | stc | registered | yes | szip | — |
| `std` | zip | std | registered | yes | szip | — |
| `sti` | zip | sti | registered | yes | szip | — |
| `stw` | zip | stw | registered | yes | szip | — |
| `svg` | standalone | svg | registered | yes | svgo, scour | validation |
| `svgz` | standalone | svgz | registered | yes | Python | validation |
| `swf` | standalone | swf | registered | yes | Python | validation |
| `sxc` | zip | sxc | registered | yes | szip | — |
| `sxd` | zip | sxd | registered | yes | szip | — |
| `sxg` | zip | sxg | registered | yes | szip | — |
| `sxi` | zip | sxi | registered | yes | szip | — |
| `sxm` | zip | sxm | registered | yes | szip | — |
| `sxw` | zip | sxw | registered | yes | szip | — |
| `tar` | tar | tar | registered | yes | szip | — |
| `tar.br` | tar.br | tar.br | registered | yes | szip | — |
| `tar.bz2` | tar.bz2 | tar.bz2 | registered | yes | szip | — |
| `tar.gz` | tar.gz | tar.gz | registered | yes | szip | — |
| `tar.gzip` | tar.gz | tar.gzip | registered | yes | szip | — |
| `tar.lz` | tar.lz | tar.lz | registered | yes | szip | — |
| `tar.lz4` | tar.lz4 | tar.lz4 | registered | yes | szip | — |
| `tar.lzma` | tar.lzma | tar.lzma | registered | yes | szip | — |
| `tar.lzo` | tar.lzo | tar.lzo | registered | yes | szip | — |
| `tar.xz` | tar.xz | tar.xz | registered | yes | szip | — |
| `tar.z` | tar.z | tar.z | registered | yes | szip | — |
| `tar.zst` | tar.zst | tar.zst | registered | yes | szip | — |
| `targa` | standalone | tga | registered | yes | Python | validation |
| `taz` | tar.z | taz | registered | yes | szip | — |
| `tbz` | tar.bz2 | tbz | registered | yes | szip | — |
| `tbz2` | tar.bz2 | tbz2 | registered | yes | szip | — |
| `template` | zip | template | registered | yes | szip | — |
| `tga` | standalone | tga | registered | yes | Python | validation |
| `tgs` | standalone | tgs | registered | yes | Python | validation |
| `tgz` | tar.gz | tgz | registered | yes | szip | — |
| `thm` | standalone | jpg | registered | yes | jpegtran | validation |
| `thmx` | zip | thmx | registered | yes | szip | — |
| `tif` | standalone | tif | registered | yes | Python | scientific |
| `tiff` | standalone | tiff | registered | yes | Python | scientific |
| `tlz` | tar.lz | tlz | registered | yes | szip | — |
| `topojson` | standalone | json | registered | yes | Python | — |
| `tracev3` | standalone | tracev3 | registered | yes | Python | tracev3 |
| `ts` | standalone | ts | registered | yes | ffmpeg, ffprobe | — |
| `tta` | standalone | tta | registered | yes | Python | — |
| `txz` | tar.xz | txz | registered | yes | szip | — |
| `tzo` | tar.lzo | tzo | registered | yes | szip | — |
| `tzst` | tar.zst | tzst | registered | yes | szip | — |
| `ui` | standalone | xml | registered | yes | Python | — |
| `unitypackage` | tar.gz | unitypackage | registered | yes | szip | — |
| `usdz` | zip | usdz | registered | yes | szip | — |
| `vdw` | zip | vdw | registered | yes | szip | — |
| `vscdb` | standalone | sqlite | registered | yes | Python | — |
| `vsd` | standalone | ole | registered | yes | Python | ole |
| `vsdm` | zip | vsdm | registered | yes | szip | — |
| `vsdx` | zip | vsdx | registered | yes | szip | — |
| `vsix` | zip | vsix | registered | yes | szip | — |
| `vssm` | zip | vssm | registered | yes | szip | — |
| `vssx` | zip | vssx | registered | yes | szip | — |
| `vstm` | zip | vstm | registered | yes | szip | — |
| `vstx` | zip | vstx | registered | yes | szip | — |
| `war` | zip | war | registered | yes | szip | — |
| `warc` | standalone | warc | registered | yes | Python | — |
| `webm` | standalone | webm | registered | yes | ffmpeg, ffprobe | — |
| `webp` | standalone | webp | registered | yes | dwebp, cwebp | validation |
| `wgt` | zip | wgt | registered | yes | szip | — |
| `whl` | zip | whl | registered | yes | szip | — |
| `wim` | wim | wim | registered | yes | szip | — |
| `wmv` | standalone | wmv | registered | yes | ffmpeg, ffprobe | — |
| `woff` | standalone | woff | registered | yes | Python | fonts |
| `woff2` | standalone | woff2 | registered | yes | Python | fonts |
| `wv` | standalone | wv | registered | yes | Python | — |
| `xap` | zip | xap | registered | yes | szip | — |
| `xapk` | zip | xapk | registered | yes | szip | — |
| `xd` | zip | xd | registered | yes | szip | — |
| `xhtml` | standalone | xml | registered | yes | Python | — |
| `xla` | standalone | ole | registered | yes | Python | ole |
| `xlam` | zip | xlam | registered | yes | szip | — |
| `xls` | standalone | ole | registered | yes | Python | ole |
| `xlsb` | zip | xlsb | registered | yes | szip | — |
| `xlsm` | zip | xlsm | registered | yes | szip | — |
| `xlsx` | zip | xlsx | registered | yes | szip | — |
| `xlt` | standalone | ole | registered | yes | Python | ole |
| `xltm` | zip | xltm | registered | yes | szip | — |
| `xltx` | zip | xltx | registered | yes | szip | — |
| `xmind` | zip | xmind | registered | yes | szip | — |
| `xml` | standalone | xml | registered | yes | Python | — |
| `xmp` | standalone | xml | registered | yes | Python | — |
| `xpi` | zip | xpi | registered | yes | szip | — |
| `xps` | zip | xps | registered | yes | szip | — |
| `xsl` | standalone | xml | registered | yes | Python | — |
| `xslt` | standalone | xml | registered | yes | Python | — |
| `xz` | standalone | xz | registered | yes | Python | — |
| `z` | standalone | z | registered | yes | Python | — |
| `zip` | zip | zip | registered | yes | szip | — |
| `zipx` | zip | zipx | registered | yes | szip | — |
| `zsav` | standalone | spss | experimental | yes | Python | scientific |
| `zst` | standalone | zst | registered | yes | Python | — |
