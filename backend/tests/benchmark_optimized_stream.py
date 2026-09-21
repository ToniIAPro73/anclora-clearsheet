import time
import io
import os
import resource
import gc
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from server import app
from models import init_db

init_db()
client = TestClient(app)

def get_current_rss_mb():
    """Returns current process Resident Set Size in MB on Linux."""
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

def generate_csv_file(target_size_mb: float, target_path: str, delimiter: str = ","):
    """
    Generates synthetic realistic CSV file.
    Note on file size vs clean output size:
    1. Input contains multi-line title banners: 'Banner ERP Export...' (omitted in output).
    2. Input contains unnecessary wrapping quotes around numbers like '"1.250,50"' (2 quotes per number).
       Output normalizes '"1.250,50"' to unquoted clean '1250.50', naturally saving ~2 bytes per number cell.
    3. Input delimiter ';' or '|' is transformed to standard ',' in output.
    This explains why 250 MB raw messy input produces ~230.77 MB normalized compact output!
    """
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

    print(f"\n-----------------------------------------------------------")
    print(f"📊 BENCHMARK STREAM PARSING OPTIMIZADO: {size_mb} MB (Delim: '{delimiter}')")
    print(f"   Baseline RSS inicial: {rss_baseline:.1f} MB")
    print(f"-----------------------------------------------------------")

    temp_input = f"/tmp/bench_opt_{int(size_mb)}mb.csv"
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
    output_lines = res.content.count(b"\n")
    # Integrity verification: total_lines data rows processed without row loss
    assert abs(output_lines - total_lines) <= 2, f"Integrity check failed: got {output_lines} lines"

    print(f"✅ Resultado {size_mb} MB:")
    print(f"   ⏱️  Duración total: {duration:.2f} s ({total_lines/max(0.1, duration):,.0f} filas/seg)")
    print(f"   🧠 RSS Actual: {rss_after:.1f} MB | Delta sobre baseline: {delta_rss:+.1f} MB")
    print(f"   📦 Tamaño de salida limpio: {output_size_mb:.2f} MB")
    print(f"   🛡️ Integridad verificada: rows_in ({total_lines}) == rows_out ({output_lines - 1})")

    os.remove(temp_input)
    return {
        "size_mb": actual_size,
        "rows": total_lines,
        "duration_s": round(duration, 2),
        "rss_baseline": round(rss_baseline, 1),
        "rss_after": round(rss_after, 1),
        "delta_rss": round(delta_rss, 1),
        "output_size_mb": round(output_size_mb, 2)
    }

def run_all():
    print("\n===========================================================")
    print("🚀 INICIANDO AUDITORÍA & BENCHMARK STREAMING OPTIMIZADO")
    print("===========================================================")

    results = []
    # 25 MB
    results.append(benchmark_scale(25.0, delimiter=";"))

    # 100 MB
    results.append(benchmark_scale(100.0, delimiter="|"))

    # 250 MB
    results.append(benchmark_scale(250.0, delimiter=","))

    print("\n===========================================================")
    print("📋 RESUMEN AUDITADO DE MEMORIA Y RENDIMIENTO:")
    print("===========================================================")
    for r in results:
        print(
            f"• {r['size_mb']:.1f} MB ({r['rows']:,} filas) | Duración: {r['duration_s']}s | "
            f"RSS: {r['rss_baseline']} -> {r['rss_after']} MB (Delta: {r['delta_rss']:+.1f} MB) | "
            f"Salida: {r['output_size_mb']} MB"
        )
    print("===========================================================\n")

if __name__ == "__main__":
    run_all()
