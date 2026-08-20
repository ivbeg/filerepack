---
title: "doctor"
description: "Show which binaries are on PATH and how to install the rest"
---
# doctor

```bash
filerepack doctor
```

Prints which binaries are on PATH and, for anything missing, OS-specific install
commands (Homebrew / MacPorts on macOS, apt / dnf / pacman / zypper / apk on
Linux, Chocolatey / winget / Scoop on Windows).

Only `7zz` or `7z` is required for archive and OOXML work. Everything else
enables extra formats. `doctor` exits `1` if the required archiver is missing.

`mp3packer` and `optivorbis` are not packaged; doctor points at their GitHub
releases.

Full notes: [External tools](/tools/). Python extras:
[Installation](/getting-started/installation#optional-extras).
