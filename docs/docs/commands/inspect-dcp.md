---
title: "inspect-dcp"
description: "Inventory a flat PyTorch Distributed Checkpoint directory without loading pickle metadata"
---

# inspect-dcp

```bash
filerepack inspect-dcp <checkpoint-directory> [OPTIONS]
```

Inventories a flat local PyTorch Distributed Checkpoint directory. `.metadata`
and rank `.distcp` shards are treated as opaque files; no pickle is deserialized
and no checkpoint is loaded or rewritten. It does not establish completeness or
native-reader compatibility.

```bash
filerepack inspect-dcp ./checkpoint --json
```

| Flag | Meaning |
| --- | --- |
| `--format-max-nodes` | File-inventory limit; default 100000 |
| `--format-timeout` | Inspection deadline in seconds; default 120 |
| `--json` | Structured inventory, including shard count, sizes and limitations |

Nested layouts, symlinks, special files and individually supplied
shards are unsupported. The source directory must contain `.metadata` and at
least one shard named `__<rank>_<index>.distcp`. No Torch installation is needed
for this passive inventory.

A completed inventory exits `0`. JSON explicitly sets `metadata_loaded`,
`complete_checkpoint_verified` and `writer_registered` to `false`; zero is not an
integrity guarantee. Unsupported layouts and path/option errors exit `1`;
argument-parser errors exit `2`.
See [model weight formats](/formats/model-weights) for the current writer gates.
