---
title: "doctor"
description: "Show resolved tools, format prerequisites and install hints"
---
# doctor

```bash
filerepack doctor
filerepack doctor --formats
filerepack doctor --json
```

Prints resolved binaries, their paths and version-probe status, and, for anything
missing, OS-specific install
commands (Homebrew / MacPorts on macOS, apt / dnf / pacman / zypper / apk on
Linux, Chocolatey / winget / Scoop on Windows).
Environment/configuration overrides take precedence over PATH lookup. A resolved
executable whose version probe fails is shown as `unverified executable`.

`--formats` prints registry-based format states and missing prerequisites.
`--json` emits a version 1 object with both `tools` and `formats`; it takes
precedence if combined with `--formats`. These diagnostics describe registered
routes and known prerequisites, not complete backend create/read qualification.

`7zz` or `7z` is required for ZIP/OOXML and generic archive work. Native CPIO
and WARC handlers do not need that archiver. `doctor` still exits `1` when it is
missing, even if the formats you intend to process do not use it. Other tools
enable their corresponding formats.

`mp3packer` and `optivorbis` are not packaged; doctor points at their GitHub
releases.

Full notes: [External tools](/tools/). Python extras:
[Installation](/getting-started/installation#optional-extras).
