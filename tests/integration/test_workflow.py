import json
import socket
from pathlib import Path

import pytest

from llm_analyzer.catalog.loader import load_catalog, load_rules
from llm_analyzer.config.settings import Settings
from llm_analyzer.hardware.base import FixtureHardwareProvider
from llm_analyzer.hardware.scanner import read_scan, scan_hardware
from llm_analyzer.recommendation.engine import analyze
from llm_analyzer.reports.generator import render_report
from llm_analyzer.schemas.results import AnalysisRequest, AnalysisResult


def test_full_fixture_workflow_without_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline workflow attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    fixture = Path(__file__).parents[1] / "fixtures/windows_nvidia_24gb_64gb.json"
    profile = read_scan(fixture)
    steps = []
    scanned = scan_hardware(FixtureHardwareProvider(profile), steps.append)
    result = analyze(
        scanned, load_catalog(), load_rules(), AnalysisRequest(use_case="coding"), Settings()
    )
    restored = AnalysisResult.model_validate(json.loads(render_report(result, "json")))
    assert restored == result
    assert steps == ["Saved hardware profile"]
    assert restored.result.recommendations


def test_fixture_provider_does_not_mutate_shared_profile(hardware):
    provider = FixtureHardwareProvider(hardware)
    profile = provider.scan()
    profile.cpu.flags.clear()
    assert hardware.cpu.flags
