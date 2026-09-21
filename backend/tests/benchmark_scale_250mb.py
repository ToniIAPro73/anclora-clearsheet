import time
import io
import os
import resource
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from server import app
from models import init_db

init_db()
client = TestClient(app)

def get_peak_memory_mb():
    # resource.getrusage returns maxrss in KB on Linux
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

def generate_csv_file(target_size_mb: float, target_path: str, delimiter: str = ","):
    """Generates synthetic messy CSV of exact target size with specified delimiter."""
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
    print(f"\n-----------------------------------------------------------")
    print(f"📊 EJECUTANDO BENCHMARK STREAM PARSING: {size_mb} MB (Delim: '{delimiter}')")
    print(f"-----------------------------------------------------------")

    temp_input = f"/tmp/bench_{int(size_mb)}mb.csv"
    actual_size, total_lines = generate_csv_file(size_mb, temp_input, delimiter=delimiter)
    print(f"Generado: {actual_size:.2f} MB (~{total_lines:,} filas)")

    mem_before = get_peak_memory_mb()
    t0 = time.time()

    # Open file stream and POST to /api/files/stream-process
    with open(temp_input, "rb") as f:
        res = client.post(
            "/api/files/stream-process",
            files={"file": (f"bench_{int(size_mb)}mb.csv", f, "text/csv")},
            data={"output_format": "csv"}
        )

    duration = time.time() - t0
    mem_after = get_peak_memory_mb()
    assert res.status_code == 200, res.text

    output_size_mb = len(res.content) / (1024 * 1024)
    print(f"✅ Resultado {size_mb} MB:")
    print(f"   ⏱️  Duración total: {duration:.2f} s ({total_lines/max(0.1, duration):,.0f} filas/seg)")
    print(f"   🧠 Peak Memory MaxRSS: {mem_after:.1f} MB (Delta: {mem_after - mem_before:.1f} MB)")
    print(f"   📦 Tamaño de salida limpio: {output_size_mb:.2f} MB")

    # Cleanup temp
    os.remove(temp_input)
    return {
        "size_mb": actual_size,
        "rows": total_lines,
        "duration_s": round(duration, 2),
        "peak_mem_mb": round(mem_after, 1),
        "output_size_mb": round(output_size_mb, 2)
    }

def run_all_scale_benchmarks():
    print("\n===========================================================")
    print("🚀 INICIANDO SUITE DE BENCHMARKS A ESCALA: 25MB, 100MB, 250MB")
    print("===========================================================")

    results = []
    # 1. Benchmark ~25 MB (with Semicolon delimiter)
    res_25 = benchmark_scale(25.0, delimiter=";")
    results.append(res_25)

    # 2. Benchmark ~100 MB (with Pipe delimiter)
    res_100 = benchmark_scale(100.0, delimiter="|")
    results.append(res_100)

    # 3. Benchmark ~250 MB (with Comma delimiter)
    res_250 = benchmark_scale(250.0, delimiter=",")
    results.append(res_250)

    print("\n===========================================================")
    print("📋 TABLA RESUMEN DE BENCHMARKS MULTI-ESCALA REALES:")
    print("===========================================================")
    for r in results:
        print(f"• {r['size_mb']:.1f} MB ({r['rows']:,} filas) | Duración: {r['duration_s']}s | Peak RSS: {r['peak_mem_mb']} MB | Salida: {r['output_size_mb']} MB")
    print("===========================================================\n")

if __name__ == "__main__":
    run_all_scale_benchmarks()
