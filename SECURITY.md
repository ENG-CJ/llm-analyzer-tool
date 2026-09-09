# Security policy

The initial 0.1.x release line is the supported scope. Report vulnerabilities through the hosting repository's private security advisory feature when enabled. If private reporting is unavailable, contact the repository maintainer privately before publishing exploit details. There is no fabricated security email address or response-time guarantee.

Normal operation is read-only with respect to hardware and does not require administrator privileges. Filesystem writes are limited to application logs, explicit scan/report output and user-invoked build/development artifacts. There is no telemetry, profile upload, driver installation, model download, server startup or account system.

The analyzer uses explicit subprocess argument arrays, timeouts and `shell=False`. Runtime paths are discovered locally; imported scan/catalog data never supplies executable paths or command strings. Do not add eval, unsafe deserialization, pickle loading or execution of model-repository code.

JSON inputs are bounded to 10 MiB and validated with strict schema versions and unknown-field rejection. HTML reports escape all imported values, and Markdown reports render imported values as literal indented content. Report publication avoids silent overwrite and uses an atomic same-filesystem hard link or replace where supported. Filesystems without hard-link support use exclusive creation, which prevents overwrite but is not crash-atomic.

The local PATH and discovered installed tools are a trust boundary: a malicious executable masquerading as a hardware/runtime probe could execute when explicitly discovered. The utility does not provide a sandbox for local executables. Built-in Windows DLLs are loaded from the system directory. No personal identifiers are intentionally queried; report sharing is always the user's choice. `config show` intentionally prints local application paths, which may contain an account directory, and is not part of a hardware report.

Debug output may contain exception paths; review it before sharing. Normal logs record diagnostic probe outcomes rather than raw command output. Public binaries are initially unsigned; verify the release source and checksum. Never disable Windows security controls to run the analyzer.
