import time
import io
import os
import resource
import gc
import pandas as pd
from fastapi.testclient import TestClient

from server import app
from models import init_db

init_db()
client = TestClient(app)

def get_current_rss_mb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

def generate_csv_file(target_size_mb: float, target_path: str, delimiter: str = ","):
    line_template = f"01/05/2026{delimiter}CLI-9012{delimiter}EMPRESA_CLIENTE_DEMO_S_L{delimiter}\"1.250,50\"{delimiter}\"262,60\"\n"
    line_bytes = line_template.encode("utf-8")
    num_lines = int((target_size_mb * 1024 * 1024) / len(line_bytes))

    header = f"Banner ERP Export {target_size_mb}MB{delimiter}{delimiter}{delimiter}{delimiter}\nFecha{delimiter}ID_Cliente{delimiter}Cliente{delimiter}Importe{delimiter}IVA\n"

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(header)
        for _ in range(num_lines):
            f.write(line_template)

    actual_size_mb = os.path.getsize(target_path) / (1024 * 1024)
    return actual_size_mb, num_lines

def benchmark_scale(size_mb: float, delimiter: str = ","):
    gc.collect()
    rss_baseline = get_current_rss_mb()

    temp_input = f"/tmp/bench_phase1_2_{int(size_mb)}mb.csv"
    actual_size, total_lines = generate_csv_file(size_mb, temp_input, delimiter=delimiter)

    t0 = time.time()
    with open(temp_input, "rb") as f:
        res = client.post(
            "/api/files/stream-process",
            files={"file": (f"bench_{int(size_mb)}mb.csv", f, "text/csv")},
            data={"output_format": "csv"}
        )
    duration = time.time() - t0

    rss_after = get_current_rss_mb()
    delta_rss = rss_after - rss_baseline
    assert res.status_code == 200, res.text

    output_size_mb = len(res.content) / (1024 * 1024)

    os.remove(temp_input)
    return {
        "size_mb": round(actual_size, 2),
        "rows": total_lines,
        "duration_s": round(duration, 2),
        "rss_baseline": round(rss_baseline, 1),
        "rss_after": round(rss_after, 1),
        "delta_rss": round(delta_rss, 1),
        "output_size_mb": round(output_size_mb, 2)
    }

def run_benchmarks():
    print("\n===========================================================")
    print("🚀 BENCHMARKS POST FASE 1 & FASE 2: 25MB, 100MB, 250MB")
    print("===========================================================")

    b25 = benchmark_scale(25.0, delimiter=";")
    print(f"• 25 MB: Duración {b25['duration_s']}s | RSS: {b25['rss_baseline']} -> {b25['rss_after']} MB (Delta: {b25['delta_rss']:+.1f} MB) | Salida: {b25['output_size_mb']} MB")

    b100 = benchmark_scale(100.0, delimiter="|")
    print(f"• 100 MB: Duración {b100['duration_s']}s | RSS: {b100['rss_baseline']} -> {b100['rss_after']} MB (Delta: {b100['delta_rss']:+.1f} MB) | Salida: {b100['output_size_mb']} MB")

    b250 = benchmark_scale(250.0, delimiter=",")
    print(f"• 250 MB: Duración {b250['duration_s']}s | RSS: {b250['rss_baseline']} -> {b250['rss_after']} MB (Delta: {b250['delta_rss']:+.1f} MB) | Salida: {b250['output_size_mb']} MB")
    print("===========================================================\n")

if __name__ == "__main__":
    run_benchmarks()
