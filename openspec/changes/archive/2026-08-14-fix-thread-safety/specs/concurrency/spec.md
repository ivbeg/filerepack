## ADDED Requirements
### Requirement: Process-Invariant Working Directory
The system SHALL NOT change the process working directory during file processing. All external tools SHALL receive their working directory via the `cwd` parameter of `subprocess.run()`.

#### Scenario: External tool in subdirectory
- **WHEN** an external tool needs to operate on files in a subdirectory (e.g., extracted archive contents)
- **THEN** the tool is invoked with `subprocess.run(args, cwd=subdir_path)`
- **AND** the process working directory remains unchanged

#### Scenario: Concurrent file processing
- **WHEN** multiple files are processed concurrently using `--jobs N`
- **THEN** each invocation operates independently without changing shared state
- **AND** no race conditions occur from working directory changes

### Requirement: Absolute Path Usage
All temporary file paths and tool argument paths SHALL be absolute paths to ensure correctness regardless of the process working directory.

#### Scenario: Temporary file creation
- **WHEN** a temporary file is created during processing
- **THEN** its path is constructed as an absolute path
- **AND** the path is valid regardless of the process working directory
