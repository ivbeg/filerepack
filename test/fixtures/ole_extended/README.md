# Additional OLE host corpus

These original binary fixtures are pinned without edits. `provenance.json`
records source URLs and repository revisions or archive identities, byte
lengths, SHA-256 and license labels. Tests verify those records. The original
DOC/XLS/PPT corpus remains in `../ole`.

- MSG/VSD/PUB/MPP: Apache POI commit
  `12c3688d130035f3dc2ca2a0f50d929456435a93`, Apache-2.0.
  `LICENSE.apache-poi` and `NOTICE.apache-poi` accompany the fixtures.
- HWP: pyhwp commit `83239f0d3bdf438b2c9f7dcff455a6e841154a39`,
  AGPL-3.0, source URLs in the manifest and `COPYING.pyhwp` included.
  This directory contains test data, not imported pyhwp implementation code.
- MSI: WiX v3 commit `ddc834a9b51b906f703f48fa6d8590681a76ad67`,
  Microsoft Reciprocal License; `LICENSE.wix3` included. MSI is never executed.
- DOC/XLS: LibreOffice core commit
  `cf80890d16f7ef318155efe5843f99153d199e07`, MPL-2.0;
  `LICENSE.libreoffice` included. These nine unchanged test files qualify
  floating PNG/JPEG/WMF layouts and a worksheet PNG. The two additional PNG
  documents re-encode the raster but do not save a 512-byte CFB sector beyond
  strict compaction. No LibreOffice implementation code is imported.
- DOC: NPOI commit `832eb28f142d54fb8a87b65fa61b5916a763b528`, Apache-2.0;
  `LICENSE.npoi` included. Two unchanged originals qualify a shared WMF and
  a large mixed store with seven eligible PNG/JPEG payloads and one opaque PNG.
- DOC: Apache Tika commit `de6af231dcb721856b719966bc010f909358319c`, Apache-2.0;
  `LICENSE.apache-tika` and `NOTICE.apache-tika` are included. The unchanged
  `testControlCharacters.doc` fixture qualifies a PNG raster and saves 17,408
  physical bytes with equal LibreOffice-rendered pages.
- DOC: NapierOne DOC-tiny subset, under the Edinburgh Napier University dataset
  license and Open Government Licence v3.0. `0018-doc.doc` (PNG+WMF),
  `0029-doc.doc` (PNG+EMF) and `0066-doc.doc` (JPEG) save 2,560, 7,168 and
  35,840 bytes respectively beyond strict compaction, with equal page renders.
- DOC: NapierOne DOC-small subset, covered by the Edinburgh Napier University
  dataset license and Open Government Licence v3.0. Its exact archive/member
  identities and required attribution are recorded in `provenance.json`;
  `LICENSE.napierone` and `NOTICE.napierone` apply. Three unchanged samples add
  three compressed EMFs, a 12-PNG store and a separate PNG, saving 73,728,
  49,664 and 45,056 bytes beyond strict CFB compaction respectively. Their
  recompressed pages match the originals rendered by LibreOffice.
- DOC: NapierOne DOC-total archive, under the same dataset and Open Government
  licences. `1825-doc.doc` combines one EMF with one raster and saves 270,848
  bytes; `4128-doc.doc` combines one EMF with nine rasters and saves 184,320
  bytes beyond strict compaction. Both render to identical LibreOffice pages.

Additional unchanged Apache POI originals qualify inline JPEG/PNG pairs
(`two_images.doc`), a floating PNG (`58804_1.doc`), an embedded metafile
(`29675.xls`) and a populated worksheet with raster drawings and scalar tertiary
fill options (`28774.xls`). `DrawingContinue.xls` and `FloatingPictures.doc` are
rejection fixtures: their current unsupported structures must not be silently
admitted. The wider 1,055-file inventories, supplemental LibreOffice QA-tree
  audit and eligibility census are recorded in `dev/ole/CORPUS.md`; each source
  has a pinned repository revision or archive/member identity and SHA-256.

Synthetic controls are constructed at test time and are clearly distinguished
from originals. They add free allocation sectors, weaker compression, repeated
identical BLIPs, populated cell/pointer records or Package wrappers to test
preservation and acceptance. They are not empirical compression estimates for
the original corpus. Fixtures/licenses are included in source distributions;
fixtures and development tools are excluded from runtime wheels.
