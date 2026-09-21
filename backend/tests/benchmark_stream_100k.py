import time
import io
import os
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from server import app
from models import init_db

init_db()
client = TestClient(app)

def run_stream_benchmark():
    print("\n=======================================================")
    print("🚀 BENCHMARK: STREAM PARSING CHUNKED CSV (100.000 FILAS)")
    print("=======================================================")

    n_rows = 100_000
    dates_pool = ["01/05/2026", "2026-05-02", "15.05.2026", "22/05/2026"]
    dates = np.random.choice(dates_pool, size=n_rows)
    amounts = [f"{(i%1000)+1}.{i%900:03d},{i%99:02d}" for i in range(n_rows)]

    df = pd.DataFrame({
        "Banner": ["INFORME STREAM CSV"] + [""]*(n_rows-1),
        "Fecha": dates,
        "Importe": amounts
    })

    csv_buf = io.BytesIO()
    df.to_csv(csv_buf, index=False)
    csv_bytes = csv_buf.getvalue()
    size_mb = len(csv_bytes) / (1024 * 1024)
    print(f"📁 Tamaño del dataset generado: {size_mb:.2f} MB ({n_rows} filas)")

    t0 = time.time()
    res = client.post(
        "/api/files/stream-process",
        files={"file": ("stream_benchmark_100k.csv", csv_bytes, "text/csv")},
        data={"output_format": "csv"}
    )
    duration = time.time() - t0

    assert res.status_code == 200
    print(f"⏱️ Tiempo total de streaming chunked: {duration:.2f}s")
    print(f"📦 Tamaño respuesta limpia: {len(res.content) / (1024*1024):.2f} MB")
    print("=======================================================\n")

if __name__ == "__main__":
    run_stream_benchmark()
