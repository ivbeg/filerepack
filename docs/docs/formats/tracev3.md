---
sidebar_position: 6
---

# Apple Unified Log tracev3

```bash
pip install 'filerepack[tracev3]'
filerepack repack archived.tracev3 --output-dir ./optimized
```

The optional isolated worker supports archived chunk streams with the 224-byte
`0x1000/0x11` header and catalog-associated `0x600d` chunksets. Inside a chunkset,
`bv41`, `bv4-` and terminal `bv4$` markers are supported. Raw LZ4 blocks use up to
64 KiB of preceding decoded bytes as their dictionary. A block is replaced only
when its independently decoded replacement is strictly smaller.

Decoded block bytes and boundaries, chunk ordering, subtypes, and every opaque
non-target chunk including padding remain unchanged. Changed chunksets update
their encoded length and zero alignment padding. Unknown markers, malformed
lengths, nonzero chunkset padding, missing dependencies and exhausted resource
budgets refuse publication. Inputs are bounded by the byte-parser memory
profile and the operation's decoded, node, scratch and deadline limits.

Writing output or backups into the active macOS Unified Log store is refused,
including filesystem aliases. A source from that store can be copied to a
separate destination, subject to source-generation verification. This command
does not process complete `.logarchive` directory packages.

This partially reverse-engineered profile follows the
[libyal format description](https://github.com/libyal/dtformats/blob/main/documentation/Apple%20Unified%20Logging%20and%20Activity%20Tracing%20formats.asciidoc)
and the [Mandiant reader](https://github.com/mandiant/macos-UnifiedLogs).
Exact decoded preservation does not constitute qualification against every
macOS log consumer or future private format variant.
