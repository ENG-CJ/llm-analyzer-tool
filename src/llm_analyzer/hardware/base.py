from collections.abc import Callable
from typing import Protocol

from llm_analyzer.schemas.hardware import HardwareScanResult

ProgressCallback = Callable[[str], None]


class HardwareProvider(Protocol):
    def scan(self, progress: ProgressCallback | None = None) -> HardwareScanResult: ...


class FixtureHardwareProvider:
    def __init__(self, profile: HardwareScanResult) -> None:
        self.profile = profile

    def scan(self, progress: ProgressCallback | None = None) -> HardwareScanResult:
        if progress:
            progress("Saved hardware profile")
        return self.profile.model_copy(deep=True)
