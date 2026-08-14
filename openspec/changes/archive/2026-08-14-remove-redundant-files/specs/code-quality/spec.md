## ADDED Requirements
### Requirement: No Redundant CLI Entry Points
The project SHALL have exactly one CLI entry point defined via `console_scripts` in `setup.py`. Duplicate CLI scripts SHALL be removed.

#### Scenario: CLI invocation
- **WHEN** a user runs `filerepack` from the terminal
- **THEN** it invokes the full-featured Typer CLI from `__main__.py`
- **AND** there is no `bin/filerepack.py` providing a duplicate, limited interface

### Requirement: Single README Format
The project SHALL maintain README documentation in Markdown format only. Outdated reStructuredText README files SHALL be removed.

#### Scenario: README access
- **WHEN** viewing the project on GitHub or PyPI
- **THEN** `README.md` is rendered as the project description
- **AND** no outdated `README.rst` exists to confuse contributors

### Requirement: Clean Build Artifacts
Stale build directories SHALL not be tracked in version control. Generated artifacts SHALL be excluded via `.gitignore`.

#### Scenario: Git status
- **WHEN** running `git status`
- **THEN** no `build/` directory contents appear as untracked files
- **AND** the working tree is clean after building
