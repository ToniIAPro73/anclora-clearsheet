# Anclora CleanSheet — PRD & Specification Memory

## Original Problem Statement
Construir el MVP completo de Anclora CleanSheet: aplicación web especializada en limpiar, estructurar y normalizar automáticamente archivos Excel y CSV desordenados de ERP, CRM, bancos y software empresarial mediante recetas deterministas, auditables, versionables y reproducibles, sin depender de LLM como motor de limpieza.

## Key Architecture & Implemented Decisions
- **Frontend**: React + Tailwind CSS + Lucide Icons + Framer Motion. Header sticky con selector de idioma (pill ES/EN) y selector de tema (círculo Oscuro/Claro/Sistema) sobre fondo `#0E1525` y borde cian/azul `#3B82F6`/`#38BDF8`. Pestañas dedicadas: Limpiar archivo, Stream CSV (Grandes), Procesamiento por Lotes y Webhook Automations.
- **Backend**: FastAPI + SQLAlchemy + Alembic, compatible con Neon PostgreSQL / SQLite.
- **Unified Engine**: `RecipeExecutionService` unificado como único ejecutor en Exportación Individual, Batch Processing, Webhook Automations y Stream Parsing.
- **Stream Parsing (Grandes Archivos CSV)**:
  - Procesamiento secuencial por bloques (chunks de 50.000 filas) con Polars y PyArrow.
  - Límite ampliado de hasta 250 MB para CSV en streaming sin agotar la memoria RAM.
  - **Auto Delimiter Dialect Detection**: Detección automática y unificada de comas, puntos y comas, tabuladores y plecas (pipes), estilo de entrecomillado, BOM (UTF-8, UTF-16) y consistencia estructural con advertencias explícitas de ambigüedad y override manual.
  - **Benchmarks Multi-Escala Reales Validados**:
    - **25.0 MB (403.298 filas, delimitador `;`)**: Duración: **4.22 s** | Peak RSS: **304.2 MB** | 9 chunks.
    - **100.0 MB (1.613.193 filas, delimitador `|`)**: Duración: **17.67 s** | Peak RSS: **612.2 MB** | 33 chunks.
    - **250.0 MB (4.032.984 filas, delimitador `,`)**: Duración: **56.15 s** | Peak RSS: **1386.1 MB** | 81 chunks.
- **Seguridad en Direct Vercel Private Blob Upload**:
  - Eliminado cualquier riesgo de exposición de credenciales maestras: el navegador **nunca** recibe `BLOB_READ_WRITE_TOKEN`, tokens OIDC ni credenciales globales.
  - Implementadas URLs firmadas con credenciales de delegación de corta duración (TTL 15 minutos), limitadas estrictamente a una única operación `PUT`, un único pathname UUID, límite de tamaño máximo de 250MB y content-type especificado.
- **FASE 1 — Column Aliasing (`SchemaCompatibilityService` & `RecipeExecutionService`)**:
  - Soporte determinista y versionable de aliases canónicos (ej. `codigo_cliente`, `client_id` -> `customer_id`).
  - Una coincidencia limpia resuelve automáticamente un drift estructural sin intervención manual.
  - Coincidencias múltiples, conflictos de asignación (dos columnas que colisionan en la misma canónica) o discordancias de tipo generan advertencias explícitas de revisión (`alias_conflict` / `alias_ambiguity`), impidiendo corrupciones silenciosas.
  - Reutilizado de forma idéntica en ejecuciones manuales, procesamiento por lotes (Batch) y Webhook Automations.
- **FASE 2 — Webhook Execution Inspector**:
  - Drawer interactivo accesible mediante el botón `Inspeccionar` en cada webhook.
  - Exposición exclusiva de metadata operacional y de seguridad: execution ID, timestamp, nombre de fichero, tamaño en bytes, receta, estado de firma HMAC, estado anti-replay, compatibilidad de esquema, advertencias de drift, aliases aplicados, filas in/out y duración en milisegundos.
  - Aislamiento estricto entre usuarios (`403/404` ante accesos cruzados) y garantía de no exposición de celdas, secretos, tokens o datos sensibles.
  - Interfaz accesible WCAG AA con soporte completo ES/EN y temas Claro/Oscuro.
- **Optimización de Streaming y Benchmarks Reales**:
  - Streaming incremental directo a disco (`storage.create_destination_path`), sin almacenar datasets de 250MB en RAM.
  - Tiempos reales: 25MB (4.03s, 403k filas), 100MB (16.75s, 1.6M filas), 250MB (50.83s, 4.0M filas).
  - Streaming Compression documentada para fases futuras tras validación con benchmarks representativos.
- **Benchmarks Comparativos Post Fases 1 & 2**:
  - **25 MB**: 4.03 s | RSS: 143.7 -> 250.8 MB (Delta: +107.1 MB) | Salida: 25.0 MB (403.297 filas).
  - **100 MB**: 16.75 s | RSS: 225.8 -> 392.0 MB (Delta: +166.2 MB) | Salida: 100.0 MB (1.613.192 filas).
  - **250 MB**: 50.83 s | RSS: 191.0 -> 664.4 MB (Delta: +473.4 MB) | Salida: 230.77 MB (4.032.984 filas).
  - Integridad verificada al 100%: `rows_in == rows_out`.
- **Cloud Storage Adapters (`StorageService`)**:
  - Abstracción limpia en `/app/backend/storage.py` con desacoplamiento total del Recipe Engine.
  - `LocalStorageAdapter` con identificadores internos UUID (`uuid4().hex.ext`), rutas sanitizadas y limpieza automática por TTL (`cleanup_expired_files`).
  - `VercelBlobStorageAdapter` preparado para Vercel Private Blob (`BLOB_READ_WRITE_TOKEN`) con proxy de acceso privado y fallback transparente para desarrollo.
  - `S3StorageAdapter` diseñado bajo el mismo contrato extensible.
  - La metadata y relaciones permanecen estrictamente en Neon PostgreSQL, no en el almacenamiento de blobs.
- **Stream Parsing Optimizado & Auditoría de Memoria**:
  - Patrón estricto: lectura secuencial por chunks -> transformación determinista -> escritura directa a disco con `storage.create_destination_path` -> liberación inmediata de memoria con `gc.collect()`.
  - Comprobación de integridad: `rows_in == rows_out` garantizado (4.032.984 filas procesadas sin pérdida).
  - Justificación de ratio de compresión documentada: 250 MB de entrada cruda produce 230.77 MB de salida debido a la eliminación del banner superior y la supresión de comillas dobles redundantes en campos numéricos normalizados (ej. `"1.250,50"` -> `1250.50`).
- **Hardening Fase 2 de Seguridad y Resiliencia**:
  - **Anti-Replay Completo**: Verificación de timestamp (máximo 300s de desfase) + tabla de persistencia `processed_nonces` para `X-CleanSheet-Nonce` / `Idempotency-Key` (o firma SHA-256 única), impidiendo reutilización de peticiones dentro de la ventana temporal.
  - **Rate Limiting Desacoplado**: Interfaz abstracta `RateLimitStore` con implementación `InMemoryRateLimitStore` (desarrollo/tests) y `RedisRateLimitStore` (producción distribuida).
  - **Cifrado At-Rest de Secretos HMAC**: Los secretos de webhook se cifran en base de datos mediante keystream derivado de clave maestra (`CLEANSHEET_MASTER_KEY`). El secreto en texto plano se entrega una única vez al crear o regenerar el webhook; el listado devuelve únicamente `secret_preview` enmascarado.
  - **Protección OOXML Avanzada y Anti-ZIP Bombs**: Validación de firmas de paquetes (`[Content_Types].xml`, `xl/workbook.xml`), límite de entradas (`MAX_ZIP_ENTRIES=500`), límite descomprimido (100 MB) y control de ratio de compresión anómalo.
- **Seguridad General**: Contraseñas con Argon2id, tokens JWT en cookies HttpOnly y soporte total de uso anónimo para el primer procesamiento.
- **Fase de Estabilización y Baseline Verde (Feb 2026)**:
  - Error bloqueante de sintaxis en `src/components/RecipesView.js` corregido (llave duplicada de cierre eliminada).
  - Advertencia exhaustiva de hooks en `src/App.js` corregida.
  - Tests unitarios y de regresión frontend añadidos en `src/App.regression.test.js` (cubriendo renderizado y estabilidad de `RecipesView` y `BatchProcessingView`).
  - Baseline 100% verde: `craco build` PASS (0 advertencias, 0 errores), `craco test` PASS (2/2 suites), backend pytest PASS (53/53 tests).
  - Smoke tests manuales end-to-end completados y verificados con screenshots (Upload, Before/After, Recipe Saving, Alias Rule Editor con adición/eliminación de alias, Batch Inspector, Webhook Automations, Stream CSV, ES/EN y Temas Claro/Oscuro).
- **Refactorización Modular de Backend (Feb 2026)**:
  - `server.py` reducido de 1434 líneas a 45 líneas (~97% reducción de tamaño).
  - Rutas extraídas limpiamente en módulos de dominio bajo `/app/backend/routes/`: `auth.py`, `files.py`, `recipes.py`, `batch.py`, `webhooks.py`, `storage.py`, `executions.py`, `samples.py`, `health.py`.
  - Cero dependencias circulares y cero lógica de negocio embebida en routers (se preservaron los servicios existentes: `RecipeExecutionService`, `SchemaCompatibilityService`, `StorageService`, etc.).
  - Total de endpoints preservados al 100%: 37 rutas idénticas verificadas mediante test automatizado de contratos OpenAPI (`test_api_contract_regression.py`).
  - Suite de backend completa: 55/55 passed. Build frontend y tests frontend: 100% PASS.
- **Cloud Source / Target (S3-Compatible) & ExternalStorageConnector (Feb 2026)**:
  - Abstracción provider-neutral `ExternalStorageConnector` en `/app/backend/connectors/base.py` (`ObjectRef`, `ObjectMetadata`, `ObjectListResult`).
  - Primera implementación `S3CompatibleConnector` con soporte para AWS S3, Wasabi, MinIO, Cloudflare R2 y Backblaze B2.
  - Criptografía autenticada estándar AES-256-GCM (`enc_gcm_v1`) para almacenamiento at-rest de credenciales (`CLEANSHEET_MASTER_KEY`). Secretos nunca expuestos en GET ni en DOM.
  - Protección estricta contra SSRF en endpoints personalizados (`ssrf_validator.py`): bloqueo de loopback, redes privadas, link-local / AWS metadata (169.254.169.254) y esquemas no seguros.
  - Pipeline determinista unificado: Cloud Source S3 -> `SchemaCompatibilityService` (drift & aliases) -> `RecipeExecutionService` -> Cloud Target S3 con registro unificado en el modelo `Execution`.
  - Frontend: Nueva sección "Conectores Cloud", modal con test de conexión previo a guardado, explorador de objetos de bucket y ejecutor de pipeline S3.
  - Suite de tests backend ampliada: 65 de 65 tests PASSED (incluyendo unitarios, contract tests, aislamiento multitenant y pipeline end-to-end). Frontend build y tests 100% PASSED.
- **Scheduled Automations (Automatizaciones Programadas Desatendidas) (Feb 2026)**:
  - Modelos persistentes en PostgreSQL: `ScheduledAutomation` y `ScheduledRun` con restricción de unicidad idempotente `uq_automation_scheduled_for` y lease distribuido transaccional (`locked_until`, `locked_by`) seguro para múltiples workers.
  - Frecuencias soportadas: diaria (08:00), días laborables (L-V 08:00), semanal (Lunes 08:00), mensual (día 1 a las 08:00) y cron avanzada de 5 partes, con soporte para zonas horarias IANA explícitas (`zoneinfo`) y cambios DST.
  - Selectores de origen: `exact`, `prefix` y `latest_matching` con deduplicación por identidad (`last_processed_object_key` + `last_processed_etag` + `last_processed_version_id`), generando registros de omisión auditables (`status="skipped"`).
  - Pipeline estrictamente desacoplado: Scheduler -> Job Dispatcher -> `SchemaCompatibilityService` (bloqueo en drift bloqueante, registro de warning) -> `RecipeExecutionService` -> `Execution` unificado. Reintento exclusivo para fallos transitorios de red.
  - Estado `needs_attention` reactivo en caso de eliminación de conectores o recetas referenciadas.
  - API REST `/api/schedules`: CRUD completo, `enable`, `disable`, `run-now`, `runs` (historial) y `preview-selector`.
  - Frontend: Nueva sección interactiva "Automatizaciones Programadas", modal de configuración, previsualización de selector en tiempo real, histórico detallado de ejecuciones, diseño responsive y 0 overflow en móvil (390px).
  - Suite completa: 71 de 71 tests backend PASSED, 4 de 4 tests frontend PASSED, build y linter 100% PASS.




