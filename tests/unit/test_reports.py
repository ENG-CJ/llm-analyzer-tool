import json

import pytest

from llm_analyzer.config.settings import ReportFormat
from llm_analyzer.recommendation.engine import analyze
from llm_analyzer.reports.generator import render_report, resolve_report_path, save_report
from llm_analyzer.schemas.results import AnalysisRequest, AnalysisResult
from llm_analyzer.utils.errors import AnalyzerError
from llm_analyzer.utils.files import atomic_write


@pytest.mark.parametrize("format", list(ReportFormat))
def test_report_formats_roundtrip(format, hardware, catalog, rules, settings, tmp_path):
    analysis = analyze(hardware, catalog, rules, AnalysisRequest(), settings)
    path = save_report(analysis, format, str(tmp_path / "تقرير é" / "report"))
    text = path.read_text(encoding="utf-8")
    if format == ReportFormat.JSON:
        assert AnalysisResult.model_validate(json.loads(text)) == analysis
    else:
        assert "methodology" in text.lower()
        assert "Confidence" in text
        assert "catalog" in text.lower()


def test_html_escapes_untrusted_hardware(hardware, catalog, rules, settings):
    hardware.cpu.brand = '<script>alert("bad")</script>'
    analysis = analyze(hardware, catalog, rules, AnalysisRequest(), settings)
    content = render_report(analysis, ReportFormat.HTML)
    assert "<script>" not in content
    assert "&lt;script&gt;" in content


def test_no_overwrite_and_force(tmp_path):
    path = tmp_path / "a.txt"
    atomic_write(path, "original")
    with pytest.raises(FileExistsError):
        atomic_write(path, "replacement")
    assert path.read_text() == "original"
    atomic_write(path, "replacement", force=True)
    assert path.read_text() == "replacement"
    assert not list(tmp_path.glob(".llm-analyzer-*"))


def test_redirected_documents(monkeypatch, tmp_path):
    from llm_analyzer.config import paths

    monkeypatch.setattr(paths, "user_documents_path", lambda: tmp_path / "مستندات")
    assert paths.report_directory() == tmp_path / "مستندات" / "Local LLM Analyzer" / "Reports"


def test_existing_and_new_report_directories(tmp_path):
    assert resolve_report_path(str(tmp_path), ReportFormat.HTML).parent == tmp_path
    new = tmp_path / "new"
    assert resolve_report_path(str(new) + "/", ReportFormat.MARKDOWN).parent == new


def test_report_permission_failure(monkeypatch, hardware, catalog, rules, settings):
    analysis = analyze(hardware, catalog, rules, AnalysisRequest(), settings)

    def fail(*a, **kw):
        raise PermissionError("denied")

    monkeypatch.setattr("llm_analyzer.reports.generator.atomic_write", fail)
    with pytest.raises(AnalyzerError) as error:
        save_report(analysis, ReportFormat.TEXT, None)
    assert error.value.code == 6
