# ANCLORA CLEANSHEET — SPECIFICATION & DOCUMENTATION

## 1. Visión del Producto
**Anclora CleanSheet** es una aplicación SaaS profesional especializada en limpiar, estructurar y normalizar automáticamente archivos Excel y CSV desordenados procedentes de ERP, CRM, bancos, software empresarial y exportaciones manuales.

La característica fundamental que diferencia a CleanSheet es:
> **Toda limpieza se convierte en una receta explícita, auditable, versionable y reproducible que puede volver a aplicarse automáticamente a futuros archivos equivalentes de forma 100% determinista.**

---

## 2. Arquitectura del Sistema
- **Frontend**: React + Tailwind CSS + Lucide Icons. Componentes modulares preparados para despliegue en Vercel.
- **Backend**: FastAPI (Python 3.11), SQLAlchemy relacional con soporte para Neon PostgreSQL y SQLite local para desarrollo rápido, motor de procesamiento determinista con Polars / Pandas y openpyxl.
- **Almacenamiento**: Abstracción `StorageService` con adaptador de archivos temporales privados y compatible con Vercel Private Blob.
- **Autenticación**: Propia, con Argon2id, tokens JWT de acceso y renovación vía cookies HttpOnly seguras.
- **Modos de Usuario**:
  - **Uso anónimo sin registro**: Carga, heurística, preview, exportación XLSX/CSV, descarga de receta YAML y script Python sin requerir cuenta.
  - **Usuario autenticado**: Persistencia en base de datos de recetas, historial de auditoría de ejecuciones y re-aplicación automatizada con fingerprinting.

---

## 3. Ejecución portable

El backend y el scheduler son procesos independientes y no requieren un daemon de cron,
una imagen privada ni servicios internos de una herramienta de desarrollo:

```bash
# Terminal 1 — API
cd backend
uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2 — Scheduled Automations
cd backend
python scheduler_worker.py
```

El worker admite `SCHEDULER_POLL_INTERVAL_SECONDS`, `SCHEDULER_BUSY_INTERVAL_SECONDS` y
`SCHEDULER_LEASE_SECONDS`. Las automatizaciones persistidas en SQLAlchemy son la fuente
canónica; los webhooks y el worker comparten leases e idempotencia.

---

## 4. Heurísticas Implementadas
1. **Detección de Filas de Título / Banners**: Identifica saltos de densidad para saltar encabezados de reportes.
2. **Cabeceras Multinivel**: Detecta categorías agrupadas y subcabeceras, aplanándolas deterministamente (`Ventas_Neto`).
3. **Múltiples Tablas por Hoja**: Identifica bloques tabulares independientes separados por filas vacías.
4. **Separadores Decimales y de Miles**: Reconoce formatos europeos (`1.250,50`) vs estadounidenses (`1,250.50`).
5. **Inconsistencias y Ambigüedades de Fechas**: Normaliza a ISO `YYYY-MM-DD` y emite advertencia de revisión ante fechas ambiguas (`01/02/2026`).
6. **Filas y Columnas Vacías**: Propone su eliminación segura sin destrucción silenciosa.
7. **Disambiguación de Cabeceras Duplicadas**: Aplica sufijos numéricos únicos (`Importe`, `Importe_2`).

---

## 5. Rendimiento (Benchmark 100.000 Filas)
- Análisis heurístico preliminar con muestreo: **~0.048s**
- Generación de vista previa interactiva: **<0.005s**
- Transformación determinista completa de 100.000 filas: **~0.80s**
- Exportación completa a CSV: **~0.11s**
- Rendimiento general: Más de 100.000 filas procesadas en menos de 1 segundo sin bloquear el navegador.

---

## 6. Criterios de Aceptación Cumplidos
- [x] Subida drag-and-drop de archivos Excel y CSV reales.
- [x] Preset Híbrido Conservador por defecto (nombres de columna conservados).
- [x] Recálculo en tiempo real con debounce en el panel de reglas.
- [x] Vista Antes / Después interactiva con inspección de celda y auditoría explicable.
- [x] Receta YAML versionada y descargable.
- [x] Script ejecutable en Python independiente con Pandas.
- [x] Validación de estructura (Structure Fingerprint) al reaplicar recetas.
- [x] Soporte bilingüe ES / EN en toda la interfaz.
- [x] Soporte de temas Claro, Oscuro y Sistema persistido en localStorage.
