---
title: "repack-store"
description: "Verify and publish a smaller complete offline local Zarr v2 store"
---

# repack-store

```bash
filerepack repack-store <store> --output-dir <parent> [OPTIONS]
```

Processes a complete offline local Zarr v2 array/group store with
`filerepack[zarr]`. The destination is `OUTPUT_PARENT/SOURCE_BASENAME` and must
be absent and disjoint from the source. All decoded chunks are compared before
exclusive atomic directory publication. No existing store is replaced.

```bash
pip install 'filerepack[zarr]'
filerepack repack-store ./data.zarr --output-dir ./optimized --dryrun --json
filerepack repack-store ./data.zarr --output-dir ./optimized --json
filerepack repack-store ./data.zarr --output-dir ./optimized --codec-policy compatible-upgrade
```

## Options

| Flag | Meaning |
| --- | --- |
| `--output-dir PATH` | Required distinct output parent |
| `--codec-policy preserve\|compatible-upgrade` | Keep compressor family/Blosc `cname` by default; compatible-upgrade permits Blosc zstd |
| `--dryrun` | Inspect without encoding, staging or predicting savings |
| `--min-savings PCT` | Required whole-store savings, finite range 0–100 |
| `--format-max-decoded-bytes` | Cumulative decoded-byte limit; default 536870912 |
| `--format-max-memory-bytes` | Memory limit; default 268435456 |
| `--format-max-scratch-bytes` | Scratch limit; default 2147483648 |
| `--format-max-nodes` | Record/chunk limit; default 100000 |
| `--format-timeout` | Deadline in seconds; default 120 |
| `--json` | Structured store outcome with compatibility and codec decisions |

Byte limits are integer bytes. This command has its own option set; file/bulk
flags such as `--overwrite`, `--profile`, `--report` and `--allow-grow` are not
accepted. Without an accepted smaller candidate, it creates no destination.

## Outcomes and limits

JSON includes `destination`, `input_bytes`, `output_bytes`, `replaced`, `reason`
and `details`. A returned inspected, unchanged or published store result exits
`0`; inspect `replaced` and `reason` to determine whether publication occurred.
Unsupported profiles and path/option errors raised by the command exit `1`;
argument-parser errors exit `2`.

V3 stores, links, object/pickle dtypes and unsupported codecs/filters are refused.
Source-generation checks require an offline store and do not implement a live
writer snapshot. Native directory publication has local macOS/APFS evidence;
Linux/Windows gates still require native CI results. See
[complete-store contracts](/formats/scientific#complete-local-zarr-stores).
