## Decisions

- Mellel uses the existing ZIP member manifest and package policy. All control
  and document bytes remain protected; outer ZIP compression is optimized.
  Embedded images remain protected in this batch because Mellel image records
  carry application-specific metadata whose rewrite contract is unverified.
- SQLite aliases use immutable read-only snapshots, refuse transaction sidecars,
  compare schema, settings, row identities and values, and publish VACUUM INTO
  only after verification. Existing SQLite routes retain their behavior.
- DuckDB copies supported offline databases into a fresh database using COPY
  FROM DATABASE with extension autoload/install and external access disabled.
  Bounded built-in scalar, list, struct and map columns, schemas and indexes
  are supported. Views, sequences, macros, custom types and unsupported Arrow
  representations are refused. Catalog definitions and ordered typed Arrow
  values, including floating-point bits, must match before publication.
- SWF validates header, frame header and complete tag framing, then compares
  exact uncompressed bytes. TGS validates bounded single-member gzip and Lottie
  JSON, retaining exact JSON bytes. Zopfli is optional; gzip level 9 is fallback.
- JSON/XML aliases reuse existing lexical preservation and parsing checks.
  Single-document JSON reading is bounded before parsing to match the existing
  256 MiB structural validation bound, including large HAR/source-map aliases.

## Limits

Native SWF and database files are bounded to 256 MiB. TGS decoding is bounded
to 4 MiB and optional Zopfli work to 1 MiB. Unsupported, active, corrupt or
unverifiable inputs remain unchanged. Application rendering is not asserted.
