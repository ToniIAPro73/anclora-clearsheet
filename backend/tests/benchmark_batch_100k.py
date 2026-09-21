import time
import io
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from server import app
from models import init_db

init_db()
client = TestClient(app)

def run_comprehensive_benchmark():
    print("\n=======================================================")
    print("🚀 INICIANDO BENCHMARK REAL: BATCH + DATASET 100.000 FILAS")
    print("=======================================================")

    # 1. Generate 100,000 rows messy dataset
    n_rows = 100_000
    dates_pool = ["01/05/2026", "2026-05-02", "15.05.2026", "22/05/2026"]
    dates = np.random.choice(dates_pool, size=n_rows)
    clients = [f"CLI-{i%500:04d}" for i in range(n_rows)]
    amounts = [f"{(i%1000)+1}.{i%900:03d},{i%99:02d}" for i in range(n_rows)]

    df_100k = pd.DataFrame({
        "Banner": ["INFORME ERP 100K ROWS"] + [""]*(n_rows-1),
        "Fecha": dates,
        "Cliente": clients,
        "Importe": amounts
    })

    csv_buf_100k = io.BytesIO()
    df_100k.to_csv(csv_buf_100k, index=False)
    csv_bytes_100k = csv_buf_100k.getvalue()
    size_mb = len(csv_bytes_100k) / (1024 * 1024)
    print(f"📊 Dataset 100.000 filas generado: {size_mb:.2f} MB")

    # 2. Benchmark Multi-file Batch Processing (including the 100k row dataset + 3 extra sheets)
    batch_small_1 = b"Titulo\nFecha,Importe\n01/05/2026,\"1.250,50\"\n02/05/2026,\"3.400,00\"\n"
    batch_small_2 = b"Extracto\nFecha,Concepto,Importe\n01/02/2026,Nomina,\"2.500,00\"\n"
    batch_small_3 = b"CRM\nNombre,Email,Fecha,Importe\nCarlos,c@a.es,01/04/2026,\"5.000,00\"\n"

    print("\n⏳ Ejecutando Batch Processing de 4 archivos (incluyendo 100.000 filas)...")
    t0 = time.time()
    res = client.post(
        "/api/batch/process",
        files=[
            ("files", ("dataset_100k.csv", csv_bytes_100k, "text/csv")),
            ("files", ("ventas_erp.csv", batch_small_1, "text/csv")),
            ("files", ("extracto_bancario.csv", batch_small_2, "text/csv")),
            ("files", ("crm_leads.csv", batch_small_3, "text/csv"))
        ],
        data={"output_format": "xlsx"}
    )
    total_batch_time = time.time() - t0

    assert res.status_code == 200
    data = res.json()
    print(f"✅ Batch completado en {total_batch_time:.2f}s")
    print(f"   Archivos procesados: {data['successful_files']} / {data['total_files']}")
    for r in data["manifest"]:
        print(f"   - {r['original_name']}: {r['status']} ({r['rows_in']} -> {r['rows_out']} filas en {r['duration_ms']}ms)")

    # 3. Benchmark Download ZIP
    t_zip_start = time.time()
    zip_res = client.get(f"/api/batch/download/{data['zip_storage_key']}")
    t_zip = time.time() - t_zip_start
    assert zip_res.status_code == 200
    zip_size_mb = len(zip_res.content) / (1024 * 1024)
    print(f"📦 Descarga ZIP completada: {zip_size_mb:.2f} MB en {t_zip*1000:.1f}ms")

    assert total_batch_time < 15.0 # High performance criterion
    print("\n=======================================================")
    print("🎯 BENCHMARK COMPLETO: RENDIMIENTO Y RESILIENCIA CONFIRMADOS")
    print("=======================================================\n")

if __name__ == "__main__":
    run_comprehensive_benchmark()
