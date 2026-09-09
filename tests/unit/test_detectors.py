import subprocess

import pytest

from llm_analyzer.hardware.windows import gpu, system
from llm_analyzer.hardware.windows.gpu import cim_gpus, parse_nvidia_csv
from llm_analyzer.runtimes import detector
from llm_analyzer.utils.process import CommandResult, run_command


def test_nvidia_csv_multiple_gpus_and_na():
    text = '0, "NVIDIA Example, Enterprise", 24576, 20480, 4096, 580.88, 8.6\n1, NVIDIA Second, 8192, [N/A], [N/A], 580.88, 8.9\n'
    # nvidia-smi uses comma-space delimiters; quoted commas are supported by the parser.
    values = parse_nvidia_csv(text.replace(', "', ',"'))
    assert len(values) == 2
    assert values[0].dedicated_vram_bytes == 24 * 1024**3
    assert values[0].name == "NVIDIA Example, Enterprise"
    assert values[1].free_vram_bytes is None
    assert values[1].evidence["free_vram_bytes"].confidence == "unknown"


def test_nvidia_missing_compute_capability():
    gpu = parse_nvidia_csv("0, NVIDIA Example, 8192, 7168, 1024, 580.88")[0]
    assert gpu.compute_capability is None


@pytest.mark.parametrize(
    "text", ["not,csv", "-1, GPU, 8192, 7168, 1024, 580.88", "0, GPU, 4096, 8192, 0, 580.88"]
)
def test_malformed_nvidia_data(text):
    with pytest.raises(ValueError):
        parse_nvidia_csv(text)


def test_cim_never_uses_adapter_ram():
    value = cim_gpus({"gpus": [{"Name": "NVIDIA Test", "AdapterRAM": 4293918720}]})[0]
    assert value.vendor == "NVIDIA"
    assert value.dedicated_vram_bytes is None


def test_nvidia_missing_command(monkeypatch):
    monkeypatch.setattr(gpu, "find_nvidia_smi", lambda: None)
    assert gpu.query_nvidia() == []


def test_nvidia_timeout_no_redundant_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(gpu, "find_nvidia_smi", lambda: "nvidia-smi")
    monkeypatch.setattr(
        gpu, "run_command", lambda args: calls.append(args) or CommandResult(error="timed out")
    )
    with pytest.raises(OSError):
        gpu.query_nvidia()
    assert len(calls) == 1


def test_nvidia_legacy_query_fallback(monkeypatch):
    responses = iter(
        [
            CommandResult(returncode=1),
            CommandResult(stdout="0, NVIDIA, 8192, 4096, 4096, 580.88", returncode=0),
        ]
    )
    monkeypatch.setattr(gpu, "find_nvidia_smi", lambda: "nvidia-smi")
    monkeypatch.setattr(gpu, "run_command", lambda args: next(responses))
    assert gpu.query_nvidia()[0].dedicated_vram_bytes == 8 * 1024**3


def test_optional_gpu_failure_keeps_cim(monkeypatch):
    def fail():
        raise OSError("inaccessible")

    monkeypatch.setattr(gpu, "enumerate_dxgi", fail)
    monkeypatch.setattr(gpu, "query_nvidia", fail)
    warnings = []
    values = gpu.gpu_info({"gpus": [{"Name": "Intel fallback"}]}, warnings)
    assert values[0].name == "Intel fallback"
    assert len(warnings) >= 2


def test_powershell_failure_is_reported(monkeypatch):
    monkeypatch.setattr(system, "run_command", lambda *a, **kw: CommandResult(error="not found"))
    with pytest.raises(OSError):
        system.query_cim()


@pytest.mark.parametrize(
    "runtime,text,expected",
    [
        ("ollama", "ollama version is 0.6.6", "0.6.6"),
        ("ollama", "Warning: client version is 0.7.0", "0.7.0"),
        ("ollama", "bad output", None),
        ("llama.cpp", "version: 5500 (abc123)", "5500"),
        ("llama.cpp", "build = 5500", "5500"),
    ],
)
def test_runtime_version_parser(runtime, text, expected):
    assert detector.parse_version(text, runtime) == expected


def test_broken_llama_cli_is_unknown(monkeypatch):
    monkeypatch.setattr(
        detector, "discover_runtime", lambda name: "llama-cli" if name == "llama.cpp" else None
    )
    monkeypatch.setattr(detector, "run_command", lambda args: CommandResult(error="timed out"))
    runtime = detector.detect_runtimes()[1]
    assert runtime.installed
    assert runtime.status == "unknown"


def test_ollama_is_not_launched(monkeypatch):
    monkeypatch.setattr(
        detector, "discover_runtime", lambda name: "ollama.exe" if name == "ollama" else None
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Ollama must not be launched during an offline scan")

    monkeypatch.setattr(detector, "run_command", forbidden)
    monkeypatch.setattr("llm_analyzer.runtimes.windows_version.file_version", lambda path: None)
    assert detector.detect_runtimes()[0].installed


def test_subprocess_safety_and_timeout(monkeypatch):
    def timeout(args, **kwargs):
        assert isinstance(args, list)
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 8
        raise subprocess.TimeoutExpired(args, 8)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert run_command(["probe", "--version"]).error == "timed out"
