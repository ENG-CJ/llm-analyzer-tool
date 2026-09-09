import hashlib
import time

import psutil

from llm_analyzer.schemas.results import BenchmarkResult


def system_benchmark(seconds: float = 1.0) -> BenchmarkResult:
    buffer = bytes(1024 * 1024)
    process = psutil.Process()
    start = time.perf_counter()
    count = 0
    peak = process.memory_info().rss
    while time.perf_counter() - start < seconds:
        hashlib.sha256(buffer).digest()
        count += 1
        if count % 64 == 0:
            peak = max(peak, process.memory_info().rss)
    elapsed = time.perf_counter() - start
    return BenchmarkResult(
        elapsed_seconds=elapsed,
        processed_bytes=count * len(buffer),
        throughput_mib_per_second=count / elapsed,
        ram_peak_bytes=peak,
    )
