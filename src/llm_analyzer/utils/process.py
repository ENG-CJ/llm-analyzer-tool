"""Bounded local process invocation. Never execute data imported from a scan."""

import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandResult:
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None


def run_command(args: list[str], timeout: float = 8) -> CommandResult:
    try:
        result = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode:
            logger.warning(
                "Probe %s returned exit code %s", os.path.basename(args[0]), result.returncode
            )
        return CommandResult(
            result.stdout.decode("utf-8-sig", errors="replace"),
            result.stderr.decode("utf-8-sig", errors="replace"),
            result.returncode,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        reason = "timed out" if isinstance(exc, subprocess.TimeoutExpired) else type(exc).__name__
        logger.warning("Probe %s failed: %s", os.path.basename(args[0]), reason)
        return CommandResult(error=reason)
