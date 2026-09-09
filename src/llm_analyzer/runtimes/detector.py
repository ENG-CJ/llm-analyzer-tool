import os
import re
import shutil
from pathlib import Path

from llm_analyzer.schemas.common import Status
from llm_analyzer.schemas.hardware import RuntimeInfo
from llm_analyzer.utils.process import run_command


def parse_version(text: str, runtime: str) -> str | None:
    if runtime == "ollama":
        match = re.search(
            r"(?:client version is|ollama version is|version[: ]+)\s*v?(\d+\.\d+\.\d+(?:[-+][\w.]+)?)",
            text,
            re.I,
        )
    else:
        match = re.search(r"(?:version:|build[: =]+)\s*(?:b)?(\d+)\b", text, re.I)
    return match.group(1) if match else None


def discover_runtime(runtime: str) -> str | None:
    names = ("ollama",) if runtime == "ollama" else ("llama-cli", "llama")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    if runtime == "ollama" and os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidate = Path(local) / "Programs/Ollama/ollama.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def detect_runtimes() -> list[RuntimeInfo]:
    runtimes: list[RuntimeInfo] = []
    for name in ("ollama", "llama.cpp"):
        executable = discover_runtime(name)
        if not executable:
            runtimes.append(
                RuntimeInfo(name=name, note="Not found on PATH or supported installation locations")
            )
            continue
        if name == "ollama":
            # ollama --version may contact the configured daemon, including a remote OLLAMA_HOST.
            # Read the PE file version instead to keep ordinary scanning strictly offline.
            from llm_analyzer.runtimes.windows_version import file_version

            version = file_version(executable) if os.name == "nt" else None
            runtimes.append(
                RuntimeInfo(
                    name=name,
                    installed=True,
                    version=version,
                    status=Status.AVAILABLE if version else Status.UNKNOWN,
                    source="executable / Windows file version",
                    note="Daemon readiness and bundled backends were not tested; no server connection made",
                )
            )
        else:
            args = [executable, "--version"]
            probe = run_command(args)
            version = parse_version(probe.stdout + "\n" + probe.stderr, name) if probe.ok else None
            runtimes.append(
                RuntimeInfo(
                    name=name,
                    installed=True,
                    version=version,
                    status=Status.AVAILABLE if version else Status.UNKNOWN,
                    note="Build/backend and model execution remain unverified"
                    if version
                    else "Version query failed, timed out or returned an unrecognized version",
                )
            )
    return runtimes
