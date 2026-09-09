# Windows releases

Use a Windows x64 machine with Python 3.11+ and an isolated development environment. PyInstaller builds for the host platform; this project only publishes Windows x64 binaries.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
.\scripts\build_windows.ps1 -Mode onedir
.\scripts\build_windows.ps1
```

The first command optionally validates a directory bundle. The final command produces `dist/llm-analyzer-windows-x64.exe` and the adjacent `.exe.sha256` checksum. Both modes include data, interpreter, dependency code and Windows version metadata; neither requests UAC elevation. Onefile extracts its embedded dependencies into a temporary directory when launched.

The build validates Windows x64/Python version, runs Ruff, strict mypy and pytest, verifies the catalog and JSON schemas, removes only the resolved in-project PyInstaller work directory, builds, smoke-tests and calculates SHA-256. `-SkipChecks` only skips lint/types/unit tests for an already-validated local diagnostic build; schema validation and binary smoke tests still run. Release CI always runs all checks.

The frozen smoke test removes Python/virtualenv locations from the child environment and PATH, changes to an unrelated temporary working directory, and checks help/version, bundled catalog, fixture recommendations, HTML reports and scan JSON including CPU flags. GitHub's hosted build runner is Windows Server, while the live provider intentionally targets Windows 10/11; local Windows 10/11 builds should additionally run `llm-analyzer scan --json`. A clean Windows VM without Python is an additional release acceptance environment; PATH isolation does not prove every Windows installation is covered.

Only `src/llm_analyzer/__init__.py` owns the application version. Packaging metadata, console version, result envelopes and Windows file-version resources derive from it. To publish the initial release after the repository is connected to GitHub:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

The workflow verifies tag/version equality, builds on `windows-latest`, attaches the executable/checksum as an Actions artifact, then creates the GitHub Release using the job-scoped GitHub token. No credentials are embedded. Local implementation/building does not create a GitHub repository or push a tag automatically.

The v1 executable is unsigned. Before broad public distribution, maintainers should test standard-user launch on Windows 10 and 11, inspect Defender/SmartScreen behavior, review bundled dependency licenses, and consider Authenticode signing. A checksum verifies file integrity against the published checksum; it is not a digital signature. Do not tell users to disable security software.
