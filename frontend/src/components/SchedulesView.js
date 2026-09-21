import React, { useState, useEffect } from "react";
import { 
  Calendar, Clock, Plus, Play, Pause, RefreshCw, Trash2, CheckCircle2, 
  AlertTriangle, History, ArrowRight, ShieldAlert, FileSpreadsheet,
  Check, Loader2, Info, Eye, ExternalLink, Settings2
} from "lucide-react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// Common IANA timezones
const COMMON_TIMEZONES = [
  "Europe/Madrid",
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "America/Sao_Paulo",
  "America/Mexico_City",
  "America/Bogota",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin"
];

export default function SchedulesView({ t, openAuthModal }) {
  const [schedules, setSchedules] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modal create/edit state
  const [showModal, setShowModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState(null);
  const [schedName, setSchedName] = useState("");
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [selectedSourceConn, setSelectedSourceConn] = useState("");
  const [sourceSelectorType, setSourceSelectorType] = useState("latest_matching");
  const [sourceKeyPattern, setSourceKeyPattern] = useState("raw/*.csv");
  const [selectedTargetConn, setSelectedTargetConn] = useState("");
  const [targetPathTemplate, setTargetPathTemplate] = useState("normalized/{source_stem}_{date}.{ext}");
  const [outputFormat, setOutputFormat] = useState("csv");
  const [scheduleType, setScheduleType] = useState("daily");
  const [cronExpression, setCronExpression] = useState("");
  const [selectedTimezone, setSelectedTimezone] = useState(
    Intl?.DateTimeFormat()?.resolvedOptions()?.timeZone || "Europe/Madrid"
  );
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [formError, setFormError] = useState(null);

  // Selector Preview State
  const [selectorPreview, setSelectorPreview] = useState(null);
  const [testingSelector, setTestingSelector] = useState(false);

  // Runs History Modal State
  const [historyModalSchedule, setHistoryModalSchedule] = useState(null);
  const [runsHistory, setRunsHistory] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(false);

  // Triggering on demand
  const [runningId, setRunningId] = useState(null);

  useEffect(() => {
    fetchSchedules();
    fetchPrerequisites();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchSchedules = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${BACKEND_URL}/api/schedules`, { withCredentials: true });
      setSchedules(res.data || []);
    } catch (err) {
      console.error("Error fetching schedules:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPrerequisites = async () => {
    try {
      const [recRes, connRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/recipes`, { withCredentials: true }),
        axios.get(`${BACKEND_URL}/api/connectors`, { withCredentials: true })
      ]);
      setRecipes(recRes.data || []);
      setConnections(connRes.data || []);

      if (recRes.data?.length > 0 && !selectedRecipeId) {
        setSelectedRecipeId(recRes.data[0].id);
      }
      if (connRes.data?.length > 0 && !selectedSourceConn) {
        setSelectedSourceConn(connRes.data[0].id);
        setSelectedTargetConn(connRes.data[0].id);
      }
    } catch (err) {
      console.error("Error fetching prerequisites:", err);
    }
  };

  const handlePreviewSelector = async () => {
    if (!selectedSourceConn || !sourceKeyPattern.trim()) {
      alert("Selecciona un conector y un patrón primero.");
      return;
    }
    setTestingSelector(true);
    setSelectorPreview(null);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/schedules/preview-selector`, {
        source_connection_id: selectedSourceConn,
        source_selector_type: sourceSelectorType,
        source_key_pattern: sourceKeyPattern.trim()
      }, { withCredentials: true });
      setSelectorPreview(res.data);
    } catch (err) {
      setSelectorPreview({ matched: false, message: err.response?.data?.detail || "Fallo probando selector." });
    } finally {
      setTestingSelector(false);
    }
  };

  const handleSaveSchedule = async (e) => {
    e.preventDefault();
    if (!schedName.trim() || !selectedRecipeId || !selectedSourceConn || !sourceKeyPattern.trim()) {
      setFormError("Por favor completa los campos obligatorios.");
      return;
    }
    setSavingSchedule(true);
    setFormError(null);

    const payload = {
      name: schedName.trim(),
      recipe_id: selectedRecipeId,
      source_connection_id: selectedSourceConn,
      source_selector_type: sourceSelectorType,
      source_key_pattern: sourceKeyPattern.trim(),
      target_connection_id: selectedTargetConn || selectedSourceConn,
      target_path_template: targetPathTemplate.trim() || "normalized/{source_stem}_{date}.{ext}",
      output_format: outputFormat,
      schedule_type: scheduleType,
      cron_expression: scheduleType === "cron" ? cronExpression.trim() : null,
      timezone_name: selectedTimezone
    };

    try {
      if (editingSchedule) {
        await axios.patch(`${BACKEND_URL}/api/schedules/${editingSchedule.id}`, payload, { withCredentials: true });
      } else {
        await axios.post(`${BACKEND_URL}/api/schedules`, payload, { withCredentials: true });
      }
      setShowModal(false);
      resetForm();
      fetchSchedules();
    } catch (err) {
      setFormError(err.response?.data?.detail || "Error guardando automatización programada.");
    } finally {
      setSavingSchedule(false);
    }
  };

  const resetForm = () => {
    setEditingSchedule(null);
    setSchedName("");
    setSourceSelectorType("latest_matching");
    setSourceKeyPattern("raw/*.csv");
    setTargetPathTemplate("normalized/{source_stem}_{date}.{ext}");
    setOutputFormat("csv");
    setScheduleType("daily");
    setCronExpression("");
    setFormError(null);
    setSelectorPreview(null);
  };

  const handleToggleActive = async (sched) => {
    try {
      const endpoint = sched.is_active ? "disable" : "enable";
      await axios.post(`${BACKEND_URL}/api/schedules/${sched.id}/${endpoint}`, {}, { withCredentials: true });
      fetchSchedules();
    } catch (err) {
      alert("Error al cambiar estado.");
    }
  };

  const handleDelete = async (schedId) => {
    if (!window.confirm("¿Seguro que deseas eliminar esta automatización programada?")) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/schedules/${schedId}`, { withCredentials: true });
      fetchSchedules();
    } catch (err) {
      alert("Error eliminando automatización.");
    }
  };

  const handleRunNow = async (schedId) => {
    setRunningId(schedId);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/schedules/${schedId}/run-now`, {}, { withCredentials: true });
      alert(res.data.status === "completed" ? "¡Ejecución completada con éxito!" : `Resultado: ${res.data.status} - ${res.data.reason || res.data.error || ""}`);
      fetchSchedules();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al ejecutar ahora.");
    } finally {
      setRunningId(null);
    }
  };

  const handleOpenHistory = async (sched) => {
    setHistoryModalSchedule(sched);
    setLoadingRuns(true);
    setRunsHistory([]);
    try {
      const res = await axios.get(`${BACKEND_URL}/api/schedules/${sched.id}/runs`, { withCredentials: true });
      setRunsHistory(res.data || []);
    } catch (err) {
      alert("Error cargando historial.");
    } finally {
      setLoadingRuns(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold dark:text-white text-slate-900 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-[#38BDF8]" />
            <span>Automatizaciones Programadas (Scheduled Cloud Runs)</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Ejecuta de forma periódica y desatendida tus recetas deterministas entre tus buckets S3 de origen y destino.
          </p>
        </div>

        <button
          data-testid="btn-open-create-schedule"
          onClick={() => {
            resetForm();
            setShowModal(true);
          }}
          className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white flex items-center space-x-1.5 shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Nueva Automatización Programada</span>
        </button>
      </div>

      {/* Main List */}
      {loading ? (
        <div className="py-12 flex justify-center">
          <Loader2 className="w-6 h-6 text-[#38BDF8] animate-spin" />
        </div>
      ) : schedules.length === 0 ? (
        <div 
          data-testid="no-schedules-notice"
          className="p-8 text-center rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white text-xs text-slate-400 space-y-2"
        >
          <Calendar className="w-8 h-8 text-slate-500 mx-auto" />
          <p className="font-semibold text-slate-300">No tienes automatizaciones programadas.</p>
          <p>Configura una tarea desatendida (diaria, semanal o cron) para procesar nuevos archivos automáticamente.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {schedules.map((sched) => (
            <div
              key={sched.id}
              data-testid={`schedule-card-${sched.id}`}
              className={`p-4 rounded-xl border transition-all ${
                sched.is_invalid
                  ? "border-amber-500/40 bg-amber-500/5"
                  : "border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white"
              } shadow-sm space-y-3`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800/80 pb-2">
                <div className="flex items-center space-x-2.5">
                  <span className={`w-2.5 h-2.5 rounded-full ${
                    sched.is_invalid
                      ? "bg-amber-400 animate-pulse"
                      : sched.is_active
                      ? "bg-emerald-400"
                      : "bg-slate-500"
                  }`} />
                  <h4 className="text-sm font-bold dark:text-white text-slate-900">
                    {sched.name}
                  </h4>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    {sched.schedule_type} ({sched.timezone_name})
                  </span>
                </div>

                {/* State Tag */}
                <div className="flex items-center space-x-2">
                  <span className={`text-[11px] font-semibold flex items-center space-x-1 ${
                    sched.is_invalid
                      ? "text-amber-400"
                      : sched.last_status === "completed"
                      ? "text-emerald-400"
                      : sched.last_status === "failed"
                      ? "text-red-400"
                      : "text-slate-400"
                  }`}>
                    {sched.is_invalid ? (
                      <>
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Needs attention</span>
                      </>
                    ) : (
                      <span>Estado: {sched.last_status}</span>
                    )}
                  </span>

                  <button
                    data-testid={`btn-toggle-schedule-${sched.id}`}
                    onClick={() => handleToggleActive(sched)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                      sched.is_active
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                        : "bg-slate-800 text-slate-400 hover:text-white"
                    }`}
                  >
                    {sched.is_active ? "Activa" : "Pausada"}
                  </button>
                </div>
              </div>

              {/* Invalid Reason Banner */}
              {sched.is_invalid && (
                <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span>{sched.last_error}</span>
                </div>
              )}

              {/* Config Details */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-400">
                <div>
                  <span className="text-[10px] text-slate-500 block">Receta y Formato:</span>
                  <span className="text-slate-200 font-medium">{sched.recipe_name} ({sched.output_format.toUpperCase()})</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">Origen ({sched.source_selector_type}):</span>
                  <span className="text-slate-200 font-mono text-[11px] truncate block">{sched.source_connection_name} / {sched.source_key_pattern}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block">Destino:</span>
                  <span className="text-slate-200 font-mono text-[11px] truncate block">{sched.target_connection_name}</span>
                </div>
              </div>

              {/* Next Runs Preview */}
              {sched.next_3_runs?.length > 0 && (
                <div className="text-[11px] bg-slate-900/60 p-2 rounded-lg border border-slate-800/80 flex flex-wrap items-center gap-x-3 gap-y-1 text-slate-400">
                  <Clock className="w-3.5 h-3.5 text-[#38BDF8]" />
                  <span>Próximas ejecuciones:</span>
                  {sched.next_3_runs.map((dt, idx) => (
                    <span key={idx} className="font-mono text-slate-300 bg-slate-800 px-1.5 py-0.5 rounded">
                      {new Date(dt).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" })}
                    </span>
                  ))}
                </div>
              )}

              {/* Actions Footer */}
              <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2">
                  <button
                    data-testid={`btn-run-now-${sched.id}`}
                    disabled={runningId === sched.id || sched.is_invalid}
                    onClick={() => handleRunNow(sched.id)}
                    className="px-3 py-1.5 rounded-lg bg-[#3B82F6]/20 hover:bg-[#3B82F6]/30 text-[#38BDF8] text-xs font-semibold flex items-center space-x-1.5 disabled:opacity-50"
                  >
                    {runningId === sched.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                    <span>Ejecutar Ahora</span>
                  </button>

                  <button
                    data-testid={`btn-history-schedule-${sched.id}`}
                    onClick={() => handleOpenHistory(sched)}
                    className="px-2.5 py-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white flex items-center space-x-1"
                  >
                    <History className="w-3.5 h-3.5" />
                    <span>Historial</span>
                  </button>
                </div>

                <button
                  data-testid={`btn-delete-schedule-${sched.id}`}
                  onClick={() => handleDelete(sched.id)}
                  className="p-1.5 rounded hover:bg-red-500/10 text-slate-400 hover:text-red-400"
                  title="Eliminar Automatización"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Create/Edit Scheduled Automation */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Calendar className="w-5 h-5 text-[#38BDF8]" />
                <h3 className="text-base font-bold dark:text-white text-slate-900">
                  {editingSchedule ? "Editar Automatización Programada" : "Nueva Automatización Programada"}
                </h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
                {formError}
              </div>
            )}

            <form onSubmit={handleSaveSchedule} className="space-y-3.5 text-xs">
              <div>
                <label className="text-slate-300 font-medium block mb-1">Nombre de la Automatización</label>
                <input
                  type="text"
                  data-testid="input-schedule-name"
                  value={schedName}
                  onChange={(e) => setSchedName(e.target.value)}
                  placeholder="ej. Ingesta Diaria Ventas ERP"
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white"
                  required
                />
              </div>

              {/* Recipe Selector */}
              <div>
                <label className="text-slate-300 font-medium block mb-1">Receta Determinista a Aplicar</label>
                <select
                  data-testid="select-schedule-recipe"
                  value={selectedRecipeId}
                  onChange={(e) => setSelectedRecipeId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white"
                  required
                >
                  {recipes.map((r) => (
                    <option key={r.id} value={r.id}>{r.name} (v{r.recipe_version || "1.0"})</option>
                  ))}
                </select>
              </div>

              {/* Source Connection & Selector */}
              <div className="p-3.5 rounded-xl border border-slate-800 bg-[#0E1525] space-y-3">
                <span className="text-xs font-bold text-[#38BDF8] block">Origen Cloud (S3)</span>
                
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Conector S3 Origen</label>
                  <select
                    data-testid="select-schedule-source-conn"
                    value={selectedSourceConn}
                    onChange={(e) => setSelectedSourceConn(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white"
                    required
                  >
                    {connections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name} ({c.config_preview?.bucket_name})</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Estrategia de Selección</label>
                    <select
                      value={sourceSelectorType}
                      onChange={(e) => setSourceSelectorType(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white"
                    >
                      <option value="latest_matching">Objeto más reciente (latest_matching)</option>
                      <option value="exact">Clave exacta (exact)</option>
                      <option value="prefix">Primer objeto de prefijo (prefix)</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Patrón / Clave S3</label>
                    <input
                      type="text"
                      data-testid="input-schedule-source-pattern"
                      value={sourceKeyPattern}
                      onChange={(e) => setSourceKeyPattern(e.target.value)}
                      placeholder="ej. raw/*.csv"
                      className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white font-mono"
                      required
                    />
                  </div>
                </div>

                {/* Test selector preview */}
                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={handlePreviewSelector}
                    disabled={testingSelector}
                    className="text-[11px] text-[#38BDF8] hover:underline flex items-center space-x-1"
                  >
                    {testingSelector ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
                    <span>Previsualizar qué archivo sería seleccionado</span>
                  </button>
                </div>

                {selectorPreview && (
                  <div className={`p-2 rounded text-[11px] ${selectorPreview.matched ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30" : "bg-amber-500/10 text-amber-300 border border-amber-500/30"}`}>
                    {selectorPreview.matched ? (
                      <span>Coincidencia encontrada: <strong>{selectorPreview.object?.key}</strong> ({((selectorPreview.object?.size_bytes || 0) / 1024).toFixed(1)} KB)</span>
                    ) : (
                      <span>{selectorPreview.message}</span>
                    )}
                  </div>
                )}
              </div>

              {/* Target Connection & Template */}
              <div className="p-3.5 rounded-xl border border-slate-800 bg-[#0E1525] space-y-3">
                <span className="text-xs font-bold text-emerald-400 block">Destino Cloud (S3)</span>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Conector S3 Destino</label>
                    <select
                      value={selectedTargetConn}
                      onChange={(e) => setSelectedTargetConn(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white"
                    >
                      {connections.map((c) => (
                        <option key={c.id} value={c.id}>{c.name} ({c.config_preview?.bucket_name})</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Formato de Salida</label>
                    <select
                      value={outputFormat}
                      onChange={(e) => setOutputFormat(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white"
                    >
                      <option value="csv">CSV (.csv)</option>
                      <option value="xlsx">Excel (.xlsx)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Plantilla de Ruta de Destino</label>
                  <input
                    type="text"
                    value={targetPathTemplate}
                    onChange={(e) => setTargetPathTemplate(e.target.value)}
                    placeholder="normalized/{source_stem}_{date}.{ext}"
                    className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white font-mono"
                  />
                  <span className="text-[10px] text-slate-500 mt-0.5 block">
                    Variables: <code>{'{source_stem}'}</code>, <code>{'{date}'}</code>, <code>{'{ext}'}</code>
                  </span>
                </div>
              </div>

              {/* Schedule and Timezone */}
              <div className="p-3.5 rounded-xl border border-slate-800 bg-[#0E1525] space-y-3">
                <span className="text-xs font-bold text-slate-200 block">Frecuencia y Zona Horaria</span>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Frecuencia</label>
                    <select
                      value={scheduleType}
                      onChange={(e) => setScheduleType(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white"
                    >
                      <option value="daily">Diaria (08:00)</option>
                      <option value="weekdays">Días laborables (L-V 08:00)</option>
                      <option value="weekly">Semanal (Lunes 08:00)</option>
                      <option value="monthly">Mensual (Día 1 a las 08:00)</option>
                      <option value="cron">Cron personalizada</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Zona Horaria (IANA)</label>
                    <select
                      value={selectedTimezone}
                      onChange={(e) => setSelectedTimezone(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white"
                    >
                      {COMMON_TIMEZONES.map((tz) => (
                        <option key={tz} value={tz}>{tz}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {scheduleType === "cron" && (
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Expresión Cron (5 partes)</label>
                    <input
                      type="text"
                      value={cronExpression}
                      onChange={(e) => setCronExpression(e.target.value)}
                      placeholder="0 8 * * *"
                      className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-white font-mono"
                    />
                  </div>
                )}
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-700">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  data-testid="btn-save-schedule-submit"
                  disabled={savingSchedule}
                  className="px-4 py-1.5 rounded-lg font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white"
                >
                  {savingSchedule ? "Guardando..." : "Guardar Automatización"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: History of Scheduled Runs */}
      {historyModalSchedule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-3xl rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <History className="w-5 h-5 text-[#38BDF8]" />
                <h3 className="text-base font-bold dark:text-white text-slate-900">
                  Historial de Ejecuciones: {historyModalSchedule.name}
                </h3>
              </div>
              <button
                onClick={() => setHistoryModalSchedule(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {loadingRuns ? (
              <div className="py-8 flex justify-center">
                <Loader2 className="w-6 h-6 text-[#38BDF8] animate-spin" />
              </div>
            ) : runsHistory.length === 0 ? (
              <p className="text-xs text-slate-400 py-6 text-center">
                Aún no hay ejecuciones registradas para esta automatización.
              </p>
            ) : (
              <div className="divide-y divide-slate-800 text-xs">
                {runsHistory.map((run) => (
                  <div key={run.id} className="py-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          run.status === "completed"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : run.status === "skipped"
                            ? "bg-amber-500/15 text-amber-400"
                            : "bg-red-500/15 text-red-400"
                        }`}>
                          {run.status} ({run.trigger_type})
                        </span>
                        <span className="text-slate-400">
                          {new Date(run.started_at).toLocaleString()}
                        </span>
                      </div>
                      <span className="font-semibold text-slate-300">
                        {run.duration_ms} ms
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-slate-400 text-[11px]">
                      <div>
                        <span className="text-slate-500 block">Origen:</span>
                        <span className="font-mono text-slate-200 truncate block">{run.source_key || "-"}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Destino:</span>
                        <span className="font-mono text-slate-200 truncate block">{run.target_key || "-"}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">Filas:</span>
                        <span className="text-slate-200">{run.rows_in} → {run.rows_out}</span>
                      </div>
                    </div>

                    {run.skip_reason && (
                      <p className="text-[11px] text-amber-300 bg-amber-500/10 p-1.5 rounded">
                        Motivo de omisión: {run.skip_reason}
                      </p>
                    )}
                    {run.error_message && (
                      <p className="text-[11px] text-red-300 bg-red-500/10 p-1.5 rounded">
                        Error: {run.error_message}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
