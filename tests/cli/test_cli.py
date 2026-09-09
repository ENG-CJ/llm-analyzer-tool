import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_analyzer.cli.app import app
from llm_analyzer.schemas.results import AnalysisResult

runner = CliRunner()
SCAN = str(Path(__file__).parents[1] / "fixtures/windows_nvidia_8gb_32gb.json")


@pytest.mark.parametrize(
    "command",
    [
        [],
        ["scan"],
        ["recommend"],
        ["analyze"],
        ["check"],
        ["report"],
        ["runtimes"],
        ["doctor"],
        ["benchmark"],
        ["catalog"],
        ["catalog", "validate"],
        ["config"],
    ],
)
def test_help(command):
    result = runner.invoke(app, [*command, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


@pytest.mark.parametrize(
    "prefix,suffix",
    [(["--json"], []), ([], ["--json"]), (["--quiet"], ["--json", "--no-color", "--no-progress"])],
)
def test_json_recommendation_is_clean(prefix, suffix):
    result = runner.invoke(
        app,
        prefix
        + ["recommend", "--scan-file", SCAN, "--use-case", "rag", "--context", "8192"]
        + suffix,
    )
    assert result.exit_code == 0, result.output
    value = AnalysisResult.model_validate_json(result.stdout)
    assert value.result.request.context == 8192
    assert "\x1b" not in result.stdout


def test_scan_json_and_output(monkeypatch, hardware, tmp_path):
    monkeypatch.setattr("llm_analyzer.cli.workflow.scan_hardware", lambda **kw: hardware)
    path = tmp_path / "hardware.json"
    result = runner.invoke(app, ["scan", "--json", "--output", str(path)])
    assert result.exit_code == 0
    assert json.loads(path.read_text()) == json.loads(result.stdout)


@pytest.mark.parametrize(
    "args",
    [
        ["recommend", "--context", "0"],
        ["check", "missing-id", "--scan-file", SCAN],
        ["check", "qwen2.5-7b-instruct", "--quant", "FAKE", "--scan-file", SCAN],
        ["recommend", "--runtime", "fake", "--scan-file", SCAN],
        ["benchmark", "--json"],
        ["recommend", "--interactive", "--scan-file", SCAN],
    ],
)
def test_input_error_exit_code(args):
    result = runner.invoke(app, args)
    assert result.exit_code == 2, result.output


@pytest.mark.parametrize(
    "args",
    [
        ["catalog", "list"],
        ["catalog", "search", "coding"],
        ["catalog", "show", "qwen2.5-7b-instruct"],
        ["catalog", "validate"],
        ["runtimes", "--scan-file", SCAN],
        ["doctor", "--scan-file", SCAN],
        ["version"],
        ["config", "show"],
    ],
)
def test_structured_commands(args):
    result = runner.invoke(app, args + ["--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["schema_version"] == "1.0"


@pytest.mark.parametrize(
    "format,extension", [("markdown", "md"), ("json", "json"), ("text", "txt"), ("html", "html")]
)
def test_report_cli(format, extension, tmp_path):
    path = tmp_path / f"report.{extension}"
    args = ["report", "--scan-file", SCAN, "--format", format, "--output", str(path), "--json"]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert json.loads(first.stdout)["schema_version"] == "1.0"
    assert "Report saved" in first.stderr
    assert path.exists()
    assert runner.invoke(app, args).exit_code == 6
    assert runner.invoke(app, args + ["--force"]).exit_code == 0


def test_default_save_report(tmp_path):
    result = runner.invoke(app, ["analyze", "--scan-file", SCAN, "--save-report", "--quiet"])
    assert result.exit_code == 0, result.output
    assert len(list((tmp_path / "Documents/Reports").glob("*.md"))) == 1


def test_default_non_tty_does_not_prompt(monkeypatch, hardware):
    monkeypatch.setattr("llm_analyzer.cli.workflow.scan_hardware", lambda **kw: hardware)
    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["hardware"]


def test_ctrl_c_is_clean(monkeypatch):
    def cancel(**kw):
        raise KeyboardInterrupt()

    monkeypatch.setattr("llm_analyzer.cli.workflow.scan_hardware", cancel)
    result = runner.invoke(app, ["scan"])
    assert result.exit_code == 130
    assert "Analysis cancelled" in result.stderr
    assert "Traceback" not in result.output


def test_config_precedence(tmp_path):
    config = tmp_path / "settings.toml"
    config.write_text(
        'default_use_case = "coding"\ndefault_context = 8192\ntop_recommendations = 2\n'
    )
    result = runner.invoke(
        app,
        ["recommend", "--scan-file", SCAN, "--config", str(config), "--context", "4096", "--json"],
    )
    assert result.exit_code == 0, result.output
    request = json.loads(result.stdout)["result"]["request"]
    assert request["context"] == 4096
    assert request["use_case"] == "coding"
    assert request["top"] == 2


def test_malformed_saved_scan_and_catalog(tmp_path):
    file = tmp_path / "bad.json"
    file.write_text("{}")
    assert runner.invoke(app, ["recommend", "--scan-file", str(file)]).exit_code == 2
    assert runner.invoke(app, ["catalog", "validate", "--catalog-file", str(file)]).exit_code == 5


def test_explicit_system_benchmark():
    result = runner.invoke(app, ["benchmark", "--yes", "--seconds", "0.1", "--json"])
    assert result.exit_code == 0, result.output
    value = json.loads(result.stdout)
    assert value["processed_bytes"] > 0
    assert value["inference_tokens_per_second"] is None


def test_unsupported_platform(monkeypatch):
    monkeypatch.setattr("llm_analyzer.hardware.scanner.platform.system", lambda: "Linux")
    assert runner.invoke(app, ["scan", "--json"]).exit_code == 3


def test_version():
    from llm_analyzer import __version__

    assert runner.invoke(app, ["--version"]).stdout.strip() == __version__


def test_version_json_wins():
    assert json.loads(runner.invoke(app, ["--json", "--version"]).stdout)["schema_version"] == "1.0"


@pytest.mark.parametrize("args", [["bogus"], ["recommend", "--not-an-option"], ["check"]])
def test_usage_errors_keep_standard_exit_code(args):
    result = runner.invoke(app, args)
    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output


def test_older_windows_rejected(monkeypatch):
    monkeypatch.setattr("llm_analyzer.hardware.scanner.platform.system", lambda: "Windows")
    monkeypatch.setattr("llm_analyzer.hardware.scanner.platform.release", lambda: "8.1")
    assert runner.invoke(app, ["scan", "--json"]).exit_code == 3
