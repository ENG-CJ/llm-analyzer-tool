"""Run the frozen executable with Python paths removed and validate structured outputs."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from llm_analyzer import __version__


def main() -> None:
    binary = Path(sys.argv[1]).resolve()
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests/fixtures/windows_nvidia_8gb_32gb.json"
    environment = dict(os.environ)
    for variable in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(variable, None)
    environment["PATH"] = str(Path(environment.get("SystemRoot", r"C:\Windows")) / "System32")
    with tempfile.TemporaryDirectory(prefix="llm-analyzer-smoke-") as directory:

        def run(*args: str) -> str:
            result = subprocess.run(
                [str(binary), *args],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode:
                raise RuntimeError(
                    f"Binary command failed ({result.returncode}): {args}\n{result.stderr}"
                )
            return result.stdout

        assert "Usage:" in run("--help")
        assert run("--version").strip() == __version__
        assert json.loads(run("catalog", "validate", "--json"))["valid"]
        report = Path(directory) / "standalone-report.html"
        analysis = json.loads(
            run(
                "recommend",
                "--scan-file",
                str(fixture),
                "--use-case",
                "rag",
                "--json",
                "--save-report",
                "--report-format",
                "html",
                "--output",
                str(report),
            )
        )
        assert analysis["result"]["recommendations"]
        assert report.read_text(encoding="utf-8").startswith("<!doctype html>")
        # GitHub's hosted Windows build runner is Windows Server, while the
        # product's live provider intentionally targets Windows 10/11. Use the
        # validated fixture here; local Windows 10/11 builds can exercise a
        # live scan separately with `llm-analyzer scan --json`.
        runtimes = json.loads(run("runtimes", "--scan-file", str(fixture), "--json"))
        assert runtimes["runtimes"], "Frozen runtime scan returned no runtime records"
        print(
            "Frozen smoke checks passed: help, version, bundled catalog, fixture analysis, HTML report and runtime scan; Python removed from child PATH"
        )


if __name__ == "__main__":
    main()
