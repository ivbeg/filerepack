# Reproducible file-format survey

This developer-only harness measures existing filerepack handlers on public files.
It does not change the runtime, add format handlers, or change the release support
matrix. The user authorized the practical survey on 2026-10-04. It supplies partial
evidence for the fixed-corpus work in
`openspec/changes/update-quality-and-specification-gates`; that broader change
remains incomplete.

## Run the pilot

From the repository root, using a Python environment with filerepack's core
dependencies, Pillow, PyArrow and optionally psutil:

```sh
python3 dev/format_survey/collect.py --run dev/format_survey/runs/pilot-2026-10-04
python3 dev/format_survey/inspect_inputs.py --run dev/format_survey/runs/pilot-2026-10-04
python3 dev/format_survey/run.py --run dev/format_survey/runs/pilot-2026-10-04
python3 -m pytest dev/format_survey/test_survey.py -q
```

The first invocation makes network requests. Optional `GH_TOKEN`/`GITHUB_TOKEN`
allows authenticated read-only API access. Credentials are never saved or sent to
raw-file downloads. A complete previously collected run reuses cached metadata
and inputs. Repository commits and configuration are frozen on first collection;
use a new run directory to refresh the selection. Failed requests are recorded and
can be retried. API limits are reported rather than interpreted as empty trees.

`config.json` chooses 12 repositories across application/library/asset/corpus
categories and ten formats. It selects up to 16 unique blobs per format, rotating
repository and size buckets in a reproducible seeded order. The bounds are 4 MiB
per input, 100 MiB total downloads, 64 MiB declared/decoded comparison payloads,
90 seconds per worker and at most 40 rendered pages per PDF. Missing integrations
and exceeded bounds produce explicit incomplete evidence.

To expand the experiment, copy the config, change `repositories`, `per_format`,
and byte/time limits, then pass `--config path/to/config.json` to the collector
with a new `--run` directory. Use the same receipt/config to compare profiles or
code versions; use a new run directory and copied frozen collection artifacts
when testing a different runtime snapshot. Existing benchmark results are cached
and do not represent a new measurement.

## Artifacts and accounting

Downloaded corpora, runtime snapshots, outputs and caches stay in ignored `runs/`.
The source files are retained; every download is checked against its frozen Git
blob SHA and gets a SHA-256 receipt. Source hashes are checked after processing.
Inputs containing LFS pointers are identified and excluded from benchmarking;
their payload sizes are not inferred from pointer-file sizes.

- `repositories.json`: pinned commits, tree IDs, selection category, licence
  identifier, stars and completeness information.
- `inventory.jsonl`, `inventory-summary.json/.csv`: regular files in complete
  trees, occurrence counts/bytes and unique blob counts/bytes. Symlinks/submodules
  are counted separately. Truncated recursive trees are fetched by subtree.
- `samples.json`: source URLs, original paths, byte limits, download outcomes,
  blob IDs, SHA-256 hashes and local input paths.
- `input-inspection.json`: content signature/parser results. These are input
  identification checks, not full format conformance or writer evidence.
- `nested-inventory.jsonl`: first-level members of sampled ZIP/NPZ inputs.
  Their decoded sizes are separate from outer-container sizes; do not add them
  to top-level storage totals. Embedded PDF/media assets are not inventoried.
- `environment.json`, `runtime/`: interpreter, packages/tools/versions, exact
  runtime-source fingerprint and source snapshot used by workers.
- `results/`, `work/`: per-case measurements, candidate outputs and worker logs.
- `benchmark-results.json`, `benchmark-summary.json/.csv`, `report.md`: evidence
  and aggregate outcomes.

The inventory is a purposive pilot, not a probability sample of GitHub. Metadata
counts are by extension; only the downloaded subset is identified by content.
There are many test fixtures, including deliberately malformed documents. Record
their source-reader outcomes rather than silently dropping them. Extension counts
do not imply independently validated formats. Repository licence metadata does
not override per-file terms; downloaded bytes are not redistributed by this code.

`preserve` uses lossless settings, JPEG/PNG metadata retention and no container
conversion. ZIP/NPZ get separate `shallow` and `deep` experiments. The historical
API option `keep_if_larger=True` **rejects** outputs that are not smaller; it is
the CLI policy with `--allow-grow` absent.

Only `verified_shrink` contributes to saved bytes. Unchanged, rejected, failed,
timed-out and independently unverifiable cases have zero verified savings and
remain in the downloaded-byte denominator. `unchanged` establishes retention of
the original bytes, not that an encoder successfully handled the input. Archive
profiles share source files and must not be summed together. Top-level actual
output sizes are used; the library's inner-candidate sizes remain separate data.

Elapsed time includes worker startup and independent comparison. Repack-only
time is recorded separately. With psutil, RSS of the worker and its live tool
descendants is sampled every 100 ms; scratch is the sampled size of its work
directory. Brief peaks can be missed. These are local sampled observations,
not exact high-water marks or hard memory/disk caps. Subprocess timeouts stop the
worker group on POSIX; Windows process-tree cleanup depends on psutil and has
not been exercised by this pilot.

## Independent comparison contracts

These comparisons do not call filerepack's acceptance validator. A pass applies
only to the following contract, on the tested backend and input variants:

| Format | Compared | Limits |
|---|---|---|
| JSON/IPYNB | Exact tokens, numeric spellings, duplicate keys, order, strings and BOM; syntax is parsed | Notebook schema/execution is not tested |
| PNG/JPEG/WebP | Every decoded frame, dimensions, duration/loop, ICC/EXIF/XMP/comment and PNG text | Pillow decoder; 16-bit multichannel PNG comparison is unavailable; other metadata has no complete contract |
| SVG | Pixel equality in rsvg-convert at 256/1024 bounding boxes | Missing renderer, DTD or external resources gives unavailable; behavior at other resolutions, accessibility and interactive DOM semantics are not established |
| PDF | Every rendered page and reported document information/forms | Poppler, 72 dpi bounded to 1600px; attachments, actions, text/search and signatures are not independently compared |
| ZIP/NPZ shallow | Ordered members, decoded member bytes, timestamps, comments and selected ZIP metadata | No extraction; bounded payloads; duplicate names unavailable; NPZ object arrays are not unpickled |
| ZIP/NPZ deep | Same archive metadata; changed members use these format-specific comparisons recursively | Four nested archive levels; unknown changed member formats unavailable; application-specific package behavior not established |
| Parquet | Decoded Arrow schema/metadata, ordered values and original file metadata | Newly added `ARROW:schema` is permitted; both encoder and comparer use PyArrow, so correlated decoder bugs and full physical-encoding equivalence are not ruled out |

For formats needing stronger application guarantees, add an independent reader
and a declared contract before counting changed candidates as verified.

## Next evidence stages

1. Review pilot exceptions and the distribution of sample sizes/source roles.
2. Provision missing comparison backends and rerun the same frozen files.
3. Expand to independent repositories, creators and variants. Keep corpus fixtures
   separate from a population/adoption sample; include realistic large files.
4. Add domain comparisons for changed nested TIFF/SQLite/application packages,
   and richer PDF/SVG metadata/application behavior.
5. Use population bytes only from a defensible target sample. Projected storage
   benefits must use byte-weighted accepted savings with zero outcomes included;
   do not extrapolate this pilot's percentages to all GitHub.
6. Select new handlers only after separately demonstrating permitted same-format
   compression and reader compatibility. PCD and VTK XML remain research
   candidates; this harness does not implement them.

Sources: [Git Trees API](https://docs.github.com/en/rest/git/trees),
[Git LFS pointers](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage),
[GitHub File History](https://github.com/andrehora/file-history),
[NapierOne](https://github.com/simonrdavies/NapierOne),
[Open Preservation format-corpus](https://github.com/openpreserve/format-corpus).
