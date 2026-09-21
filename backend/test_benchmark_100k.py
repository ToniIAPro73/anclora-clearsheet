import time
import io
import pandas as pd
import numpy as np
from engine import NormalizationPlanner, TransformationEngine

def test_100k_rows_performance():
    print("\n--- INICIANDO BENCHMARK DE 100.000 FILAS ---")
    start_gen = time.time()
    n_rows = 100_000

    # Synthetic realistic messy ERP data:
    # 2 Title rows + 100,000 data rows with European decimals and mixed dates
    dates_pool = ["01/05/2026", "2026-05-02", "15.05.2026", "22/05/2026"]
    dates = np.random.choice(dates_pool, size=n_rows)
    clients = [f"CLI-{i%500:04d}" for i in range(n_rows)]
    amounts = [f"{(i%1000)+1}.{i%900:03d},{i%99:02d}" for i in range(n_rows)]
    taxes = [f"{((i%1000)+1)*0.21:.2f}".replace(".", ",") for i in range(n_rows)]

    raw_data = [
        ["INFORME ERP 100K ROWS ANCLORA CLEANSHEET", "", "", ""],
        ["Generado: 2026-05-01", "Dpto: Finanzas", "", ""],
        ["Fecha", "ID_Cliente", "Importe_Neto", "IVA_21%"]
    ]

    for d, c, a, t in zip(dates, clients, amounts, taxes):
        raw_data.append([d, c, a, t])

    gen_time = time.time() - start_gen
    print(f"1. Generación de {n_rows} filas: {gen_time:.2f}s")

    # Step 1: Analysis & Heuristics (sampling & header detection)
    start_analysis = time.time()
    plan = NormalizationPlanner.plan(raw_data)
    analysis_time = time.time() - start_analysis
    print(f"2. Análisis heurístico y planificación: {analysis_time:.3f}s")

    assert plan["header_row_index"] == 2
    assert plan["total_data_rows"] == n_rows

    # Step 2: Transformation Engine (vectorized operations & chunking)
    start_transform = time.time()
    # In engine, transform sample for preview is instant (<0.05s)
    preview = TransformationEngine.apply_rules(raw_data[:200], plan["default_rules"])
    preview_time = time.time() - start_transform
    print(f"3. Generación de vista previa interactiva (sample): {preview_time:.3f}s")

    # Step 3: Full dataset batch execution (all 100,000 rows)
    start_full = time.time()
    full_transformed = TransformationEngine.apply_rules(raw_data, plan["default_rules"])
    full_transform_time = time.time() - start_full
    print(f"4. Transformación determinista completa de 100.000 filas: {full_transform_time:.2f}s")

    # Step 4: Export to CSV / XLSX
    start_export = time.time()
    df_clean = pd.DataFrame(full_transformed["rows"], columns=full_transformed["headers"])
    buf = io.BytesIO()
    df_clean.to_csv(buf, index=False)
    csv_export_time = time.time() - start_export
    print(f"5. Exportación completa a CSV (100.000 filas): {csv_export_time:.2f}s")

    assert len(full_transformed["rows"]) == n_rows
    assert full_transform_time < 5.0 # Required high performance
    print("--- BENCHMARK 100K COMPLETADO SATISFACTORIAMENTE ---")

if __name__ == "__main__":
    test_100k_rows_performance()
