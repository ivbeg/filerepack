# Additional hosts over the existing strict CFB backend

## Decisions

### Bounded host profiles

Use a small explicit profile registry over the existing inspector/writer rather
than automatic support for every CFB file. Every entry defines extensions,
recognized versions/structure, required streams/storages, protection/signature
locations, unsupported feature flags and qualified CFB naming/metadata rules.
No broad capability-registry refactor is required; integration with the pending
registry proposal can follow without making this change depend on its delivery.

| Host | Initial identification and qualification work |
| --- | --- |
| MSG | Property streams, recipients, attachment storages and message class; distinguish embedded messages and retain every property/attachment byte. |
| VSD | Binary Visio document/version streams; use HDGF/libvisio as read-only qualification aids for the exact supported versions. |
| PUB | Publisher version/Contents/Quill structure; use HPBF/libmspub as read-only aids and preserve all private streams. |
| MPP | Project version-specific stream layout; use MPXJ as a reader and preserve raw task/resource/calendar data, not a normalized re-export. |
| MSI | Installer database and summary structures, encoded stream names and signature locations; retain tables and embedded CAB streams unchanged. |
| HWP 5 | FileHeader signature/version/flags plus DocInfo and section/storage layout; distinguish HWP 3/HWPX, protection, distribution and scripts. |

The table is a qualification agenda, not an assertion that these readers provide
complete lossless writers or signature gates. Record exact parser/tool versions,
licenses, feature boundaries and primary evidence in each completed profile.
Enable only versions demonstrated by the profile's complete checks.

### Protection and backend compatibility

Audit signatures/encryption/rights/distribution markers for each host instead of
applying Office-specific flags indiscriminately. Retain the conservative existing
policy for authenticated or incompletely inspected containers; recognize the
scope of an embedded signed attachment separately from a container signature.
No signature is removed or declared valid from parsing alone. Embedded protected
content copied verbatim can be admitted only when the host profile proves that
its authenticated bytes and references are unaffected.

Keep CFB v3 validation/allocation/name/metadata bounds. If a real host uses an
unqualified naming or metadata variant, skip it or qualify that exact additional
variant with independent/native tests. Do not bypass constraints for MSI's encoded
names or normalize any stream name/property value. Required backend/independent
reader capabilities are checked before creating a publishable candidate.

### Dispatch, preservation and fallback

Register only the six named extension families, and verify actual host structure
after routing. A renamed arbitrary CFB, HTML/XLS-style impostor or newer ZIP-based
variant cannot pass from its suffix. All live stream bytes, empty objects,
hierarchy, names, CLSIDs, state bits and times remain identical; compressed
payloads and application history are opaque and unchanged.

The existing strict OLE verifier independently compares complete manifests and
validates the candidate's same host profile. No application-level resave is used
for writing. Standalone and archive-member paths share staging, source/output
policies, native process supervision and root budgets. Physical-size no-ops are
reported separately from unsupported/missing-backend inputs.

## Qualification and rollout

Begin with documented MSG and HWP layouts, then enable each remaining host
independently after its audit. Use originals plus controlled free-sector variants,
non-ASCII names, private/empty/property streams and metadata extremes. Test altered
stream bytes, missing entries and name/CLSID/time changes. Use corresponding
readers and available applications with active content disabled; unavailable
applications/platforms remain explicit limits. Existing Office fixtures remain
regressions. Rollback removes only individual new profile registrations.

## Primary references

- [MSG structure](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxmsg/1a69e000-f391-4c03-9d43-32d5f554bca7)
- [Apache POI components and format readers](https://poi.apache.org/components/index.html)
- [MPXJ MPP reader](https://www.mpxj.org/apidocs/org/mpxj/mpp/MPPReader.html)
- [Windows Installer storage](https://learn.microsoft.com/en-us/visualstudio/extensibility/internals/windows-installer-basics?view=visualstudio)
- [Installer stream naming](https://learn.microsoft.com/en-us/windows/win32/msi/ole-limitations-on-streams)
- [Hancom HWP structure](https://blog.hancom.com/en/hwp-hwpx-data-extraction-format-library/)
- [Existing qualified CFB contract](../add-ole-container-compaction/specs/ole-compaction/spec.md)
