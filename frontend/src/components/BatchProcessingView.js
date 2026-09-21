import React, { useState, useEffect } from "react";
import { Files, Download, Loader2, CheckCircle2, FileSpreadsheet, ArrowRight, Archive, Activity, Clock, AlertTriangle } from "lucide-react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function BatchProcessingView({ t, openAuthModal }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [outputFormat, setOutputFormat] = useState("xlsx");
  const [processing, setProcessing] = useState(false);
  const [results, setResults] = useState(null);

  // Batch Execution Inspector state
  const [pastBatches, setPastBatches] = useState([]);
  const [selectedBatchDetail, setSelectedBatchDetail] = useState(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [loadingPastBatches, setLoadingPastBatches] = useState(false);

  useEffect(() => {
    fetchRecipes();
    fetchPastBatches();
  }, []);

  const fetchPastBatches = async () => {
    try {
      setLoadingPastBatches(true);
      const res = await axios.get(`${BACKEND_URL}/api/batch/executions`, { withCredentials: true });
      setPastBatches(res.data || []);
    } catch (e) {
      // ignore
    } finally {
      setLoadingPastBatches(false);
    }
  };

  const fetchRecipes = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/recipes`, { withCredentials: true });
      setRecipes(res.data || []);
    } catch (e) {
      // ignore
    }
  };

  const handleFilesChange = (e) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files));
      setResults(null);
    }
  };

  const handleRunBatch = async () => {
    if (selectedFiles.length === 0) return;
    setProcessing(true);
    setResults(null);

    try {
      const formData = new FormData();
      selectedFiles.forEach((file) => {
        formData.append("files", file);
      });
      if (selectedRecipeId) {
        formData.append("recipe_id", selectedRecipeId);
      }
      formData.append("output_format", outputFormat);

      const res = await axios.post(`${BACKEND_URL}/api/batch/process`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        withCredentials: true
      });
      setResults(res.data);
      fetchPastBatches();
    } catch (err) {
      alert("Error al procesar lote de archivos.");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold dark:text-white text-slate-900 flex items-center gap-2">
          <Files className="w-5 h-5 text-[#38BDF8]" />
          <span>{t.nav.batch}</span>
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Sube múltiples archivos Excel o CSV desordenados y normalízalos de forma simultánea con un solo clic.
        </p>
      </div>

      {/* Upload Box for Multiple Files */}
      <div
        data-testid="batch-upload-dropzone"
        className="p-8 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-800 dark:bg-[#0B1220] bg-white text-center space-y-4"
      >
        <div className="w-12 h-12 rounded-xl bg-[#3B82F6]/15 flex items-center justify-center mx-auto text-[#38BDF8]">
          <Files className="w-6 h-6" />
        </div>
        <div>
          <h4 className="text-sm font-bold dark:text-white text-slate-900">
            Selecciona varios archivos Excel o CSV
          </h4>
          <p className="text-xs text-slate-400 mt-1">
            Puedes seleccionar varios ficheros simultáneamente arrastrándolos o con Ctrl / Shift.
          </p>
        </div>

        <input
          type="file"
          multiple
          accept=".xlsx,.csv,.xls"
          data-testid="batch-file-input"
          onChange={handleFilesChange}
          className="text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[#3B82F6] file:text-white hover:file:bg-[#2563EB] cursor-pointer"
        />

        {selectedFiles.length > 0 && (
          <div className="pt-2 text-xs font-semibold text-[#38BDF8]">
            {selectedFiles.length} archivos seleccionados listos para procesar
          </div>
        )}
      </div>

      {/* Configuration Bar */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div>
            <label className="text-slate-400 font-medium block mb-1">Receta a aplicar:</label>
            <select
              data-testid="batch-recipe-select"
              value={selectedRecipeId}
              onChange={(e) => setSelectedRecipeId(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
            >
              <option value="">Auto-planificar por archivo (Preset Conservador)</option>
              {recipes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} (v{r.recipe_version})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-slate-400 font-medium block mb-1">Formato de salida:</label>
            <select
              data-testid="batch-format-select"
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
            >
              <option value="xlsx">Excel (.xlsx)</option>
              <option value="csv">CSV (.csv)</option>
            </select>
          </div>
        </div>

        <button
          data-testid="run-batch-process-btn"
          onClick={handleRunBatch}
          disabled={selectedFiles.length === 0 || processing}
          className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center space-x-2 transition-all shadow-md shadow-[#3B82F6]/20 self-start sm:self-auto"
        >
          {processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          <span>{processing ? "Procesando Lote..." : "Procesar Todo el Lote"}</span>
        </button>
      </div>

      {/* Results View */}
      {results && (
        <div
          data-testid="batch-results-container"
          className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm space-y-4"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3 gap-2">
            <div className="flex items-center space-x-3 text-xs font-bold">
              <span className="text-emerald-400 flex items-center space-x-1">
                <CheckCircle2 className="w-4 h-4" />
                <span>{results.successful_files ?? results.total_files} procesados correctamente</span>
              </span>
              {results.failed_files > 0 && (
                <span className="text-rose-400">
                  ({results.failed_files} con incidencias registradas en manifest)
                </span>
              )}
            </div>

            <a
              data-testid="download-batch-zip-btn"
              href={`${BACKEND_URL}${results.zip_download_url}`}
              download
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-600 text-white flex items-center space-x-1.5 shadow-sm self-start sm:self-auto"
            >
              <Archive className="w-3.5 h-3.5" />
              <span>Descargar ZIP (con manifest.json y manifest.csv)</span>
            </a>
          </div>

          <div className="divide-y divide-slate-100 dark:divide-slate-800/80 text-xs">
            {results.results.map((item, idx) => (
              <div key={idx} className="py-2.5 flex items-center justify-between">
                <div className="flex items-center space-x-2 font-medium dark:text-slate-200 text-slate-800">
                  <FileSpreadsheet className="w-4 h-4 text-[#38BDF8]" />
                  <span>{item.original_name}</span>
                  <span className="text-slate-400">→</span>
                  <span className="text-[#38BDF8]">{item.clean_name}</span>
                </div>
                <div className="flex items-center space-x-4 text-slate-500">
                  <span>{item.rows_in} filas</span>
                  <span className="text-emerald-400 font-semibold">{item.changes_count} cambios</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phase 2: Batch Execution History & Inspector Section */}
      <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold dark:text-white text-slate-900 flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#38BDF8]" />
              <span>Inspector de Lotes Históricos</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Auditoría y manifest operacional de ejecuciones multi-archivo anteriores.
            </p>
          </div>
        </div>

        {pastBatches.length === 0 ? (
          <div
            data-testid="no-past-batches-notice"
            className="p-8 text-center rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white text-xs text-slate-400"
          >
            No hay lotes previos registrados en tu cuenta.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {pastBatches.map((b) => (
              <div
                key={b.batch_id}
                data-testid={`batch-history-card-${b.batch_id}`}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white flex flex-col justify-between space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#38BDF8] text-[11px] truncate max-w-[250px]">
                    {b.recipe_name}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                    b.status === "completed"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : b.status === "partial_success"
                      ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                      : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                  }`}>
                    {b.status?.toUpperCase()}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                  <div>
                    <span>Archivos: </span>
                    <strong className="text-slate-800 dark:text-slate-200">{b.successful_count} / {b.total_files}</strong>
                  </div>
                  <div>
                    <span>Filas Out: </span>
                    <strong className="text-slate-800 dark:text-slate-200">{b.rows_out}</strong>
                  </div>
                  <div>
                    <span>Duración: </span>
                    <strong className="text-slate-800 dark:text-slate-200">{b.duration_ms} ms</strong>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400">
                    {new Date(b.created_at).toLocaleString()}
                  </span>

                  <button
                    data-testid={`btn-inspect-batch-${b.batch_id}`}
                    onClick={() => {
                      setSelectedBatchDetail(b);
                      setInspectorOpen(true);
                    }}
                    className="px-2.5 py-1 rounded bg-[#3B82F6]/15 hover:bg-[#3B82F6]/25 text-[#38BDF8] font-semibold text-[11px]"
                  >
                    Ver Manifest Completo
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Batch Inspector Drawer / Modal */}
      {inspectorOpen && selectedBatchDetail && (
        <div
          data-testid="batch-inspector-overlay"
          className="fixed inset-0 z-50 flex items-center justify-end p-0 bg-black/60 backdrop-blur-sm"
        >
          <div
            data-testid="batch-inspector-drawer"
            className="w-full max-w-2xl h-full border-l border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl flex flex-col justify-between overflow-y-auto space-y-4"
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Activity className="w-5 h-5 text-[#38BDF8]" />
                  <div>
                    <h3 className="text-base font-bold dark:text-white text-slate-900">
                      Inspector de Ejecución de Lote (Batch Manifest)
                    </h3>
                    <p className="text-xs text-slate-400">
                      ID: {selectedBatchDetail.batch_id} • Receta: {selectedBatchDetail.recipe_name}
                    </p>
                  </div>
                </div>
                <button
                  data-testid="close-batch-inspector-btn"
                  onClick={() => setInspectorOpen(false)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  ✕
                </button>
              </div>

              {/* Batch High-Level Metrics Banner */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-xl bg-slate-100 dark:bg-[#0E1525] text-xs">
                <div>
                  <span className="text-slate-400 text-[10px] block">Archivos:</span>
                  <span className="font-bold text-slate-800 dark:text-white">
                    {selectedBatchDetail.successful_count} OK / {selectedBatchDetail.failed_count} Error
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Filas Totales:</span>
                  <span className="font-bold text-[#38BDF8]">
                    {selectedBatchDetail.rows_in} → {selectedBatchDetail.rows_out}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Duración Total:</span>
                  <span className="font-bold text-slate-800 dark:text-white">
                    {selectedBatchDetail.duration_ms} ms
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Estado Consolidado:</span>
                  <span className="font-bold text-emerald-400">
                    {selectedBatchDetail.status?.toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Individual File Records from Manifest */}
              <div className="space-y-2">
                <span className="font-bold text-slate-700 dark:text-slate-300 block text-xs uppercase tracking-wider">
                  Detalle del Manifest ({selectedBatchDetail.manifest?.length || 0} archivos):
                </span>

                <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                  {selectedBatchDetail.manifest?.map((item, mIdx) => (
                    <div
                      key={mIdx}
                      data-testid={`manifest-row-${mIdx}`}
                      className={`p-3 rounded-xl border text-xs font-mono space-y-1.5 ${
                        item.status === "completed"
                          ? "border-slate-200 dark:border-slate-800 dark:bg-[#0E1525] bg-slate-50"
                          : "border-rose-500/30 bg-rose-500/10 text-rose-300"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800 dark:text-slate-200">
                          {item.original_name}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          item.status === "completed" ? "text-emerald-400 bg-emerald-500/10" : "text-rose-400 bg-rose-500/20"
                        }`}>
                          {item.status?.toUpperCase()} ({item.duration_ms} ms)
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] font-sans text-slate-500 dark:text-slate-400">
                        <div>
                          <span>Filas: </span>
                          <strong className="text-slate-700 dark:text-slate-300">{item.rows_in} → {item.rows_out}</strong>
                        </div>
                        {item.transformations_count !== undefined && (
                          <div>
                            <span>Transformaciones: </span>
                            <span className="text-[#38BDF8]">{item.transformations_count}</span>
                          </div>
                        )}
                      </div>

                      {item.warnings && (
                        <div className="text-[11px] text-amber-400 font-sans p-1.5 rounded bg-amber-500/10">
                          ⚠ {item.warnings}
                        </div>
                      )}

                      {item.error && (
                        <div className="text-[11px] text-rose-400 font-sans p-1.5 rounded bg-rose-500/15">
                          Error sanitizado: {item.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end">
              <button
                onClick={() => setInspectorOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200"
              >
                Cerrar Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
