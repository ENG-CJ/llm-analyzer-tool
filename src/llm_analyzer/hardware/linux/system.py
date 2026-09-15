from __future__ import annotations

import platform

from llm_analyzer.schemas.hardware import PlatformInfo


def collect_platform() -> PlatformInfo:
    machine = platform.machine()

    return PlatformInfo(
        os="Linux",
        version=platform.release(),
        build=None,
        edition=None,
        architecture=machine,
        machine_architecture=machine,
        manufacturer=None,
        model=None,
    )