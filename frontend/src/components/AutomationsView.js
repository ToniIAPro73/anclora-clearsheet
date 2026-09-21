import React, { useState, useEffect } from "react";
import { Zap, Plus, Trash2, Copy, Check, Link2, Clock, Globe, Eye, ShieldCheck, Activity } from "lucide-react";
import axios from "axios";
import { useAuth } from "../context/AuthContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function AutomationsView({ t, openAuthModal }) {
  const { user } = useAuth();
  const [automations, setAutomations] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [recipeId, setRecipeId] = useState("");
  const [schedule, setSchedule] = useState("on_webhook");
  const [targetFormat, setTargetFormat] = useState("xlsx");
  const [copiedToken, setCopiedToken] = useState(null);

  // Webhook Inspector Drawer state
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorData, setInspectorData] = useState(null);
  const [loadingInspector, setLoadingInspector] = useState(false);

  useEffect(() => {
    if (user) {
      fetchData();
    } else {
      setLoading(false);
    }
  }, [user]);

  const fetchData = async () => {
    try {
      const [autoRes, recRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/automations`, { withCredentials: true }),
        axios.get(`${BACKEND_URL}/api/recipes`, { withCredentials: true })
      ]);
      setAutomations(autoRes.data || []);
      setRecipes(recRes.data || []);
      if (recRes.data && recRes.data.length > 0) {
        setRecipeId(recRes.data[0].id);
      }
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAutomation = async (e) => {
    e.preventDefault();
    if (!name.trim() || !recipeId) return;

    try {
      await axios.post(
        `${BACKEND_URL}/api/automations`,
        {
          name: name.trim(),
          recipe_id: recipeId,
          target_format: targetFormat
        },
        { withCredentials: true }
      );
      setModalOpen(false);
      setName("");
      fetchData();
    } catch (err) {
      alert("Error al crear automatización.");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Seguro que deseas eliminar este webhook?")) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/automations/${id}`, { withCredentials: true });
      setAutomations(automations.filter((a) => a.id !== id));
    } catch (e) {
      alert("Error al eliminar.");
    }
  };

  const copyWebhookUrl = (token) => {
    const fullUrl = `${BACKEND_URL}/api/webhooks/drop/${token}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-4">
        <Zap className="w-12 h-12 text-[#38BDF8] mx-auto opacity-70" />
        <h3 className="text-lg font-bold dark:text-white text-slate-900">
          Automatizaciones y Webhook Drops
        </h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Inicia sesión para generar webhooks seguros y programar la limpieza automática de hojas recurrentes desde tu ERP, Zapier o cron jobs.
        </p>
        <button
          onClick={openAuthModal}
          className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white"
        >
          {t.nav.sign_in}
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold dark:text-white text-slate-900 flex items-center gap-2">
            <Zap className="w-5 h-5 text-[#38BDF8]" />
            <span>Automatizaciones & Webhook Drops</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Recibe archivos sucios vía HTTP POST, aplica tu receta determinista y devuelve automáticamente el archivo normalizado.
          </p>
        </div>

        <button
          data-testid="create-automation-btn"
          onClick={() => setModalOpen(true)}
          disabled={recipes.length === 0}
          className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-40 text-white flex items-center space-x-1.5 shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>Nuevo Webhook Drop</span>
        </button>
      </div>

      {recipes.length === 0 && (
        <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs">
          Debes guardar al menos una receta en tu cuenta para poder crear automatizaciones.
        </div>
      )}

      {automations.length === 0 ? (
        <div
          data-testid="automations-empty-state"
          className="p-12 text-center rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white space-y-3"
        >
          <Zap className="w-12 h-12 text-slate-400 mx-auto opacity-50" />
          <h4 className="text-base font-bold dark:text-white text-slate-800">
            No tienes automatizaciones configuradas
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Crea un endpoint de webhook para conectar tus sistemas empresariales y limpiar hojas automáticamente al generarse.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {automations.map((auto) => (
            <div
              key={auto.id}
              data-testid={`automation-card-${auto.id}`}
              className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>Activo</span>
                </span>
                <span className="text-xs text-slate-500">{auto.runs_count} ejecuciones</span>
              </div>

              <div>
                <h4 className="text-sm font-bold dark:text-white text-slate-900">{auto.name}</h4>
                <p className="text-xs text-[#38BDF8] mt-0.5">Receta: {auto.recipe_name}</p>
              </div>

              {/* Webhook URL Endpoint Box */}
              <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-[#080D18] flex items-center justify-between text-xs font-mono">
                <span className="truncate text-slate-700 dark:text-slate-300 mr-2">
                  {BACKEND_URL}/api/webhooks/drop/{auto.token}
                </span>
                <button
                  data-testid={`copy-webhook-${auto.id}`}
                  onClick={() => copyWebhookUrl(auto.token)}
                  className="p-1 rounded text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors flex-shrink-0"
                  title="Copiar URL de Webhook"
                >
                  {copiedToken === auto.token ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

              {/* HMAC Secret Key Box */}
              <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-100/60 dark:bg-[#0E1525] text-[11px] font-mono flex items-center justify-between">
                <div className="truncate mr-2">
                  <span className="text-slate-400 font-sans block text-[10px]">HMAC Secret (Cifrado At-Rest):</span>
                  <span className="text-[#38BDF8] select-all font-semibold">
                    {auto.secret_key || auto.secret_preview || "••••••••••••••••"}
                  </span>
                  {auto.secret_key && (
                    <span className="text-[10px] text-amber-400 block font-sans">
                      (Copia este secreto ahora; no se volverá a mostrar completo por seguridad)
                    </span>
                  )}
                </div>
              </div>

              {/* cURL Usage Snippet with Signed Header Example */}
              <div className="text-[11px] text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-[#0E1525] p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 font-mono leading-relaxed overflow-x-auto">
                <div className="text-[10px] text-slate-400 mb-1 font-sans">Llamada autenticada con HMAC:</div>
                curl -X POST -F "file=@ventas.xlsx" \<br />
                &nbsp;&nbsp;-H "X-CleanSheet-Timestamp: $(date +%s)" \<br />
                &nbsp;&nbsp;-H "X-CleanSheet-Signature: t=$(date +%s),v1=&lt;hmac_sha256&gt;" \<br />
                &nbsp;&nbsp;{BACKEND_URL}/api/webhooks/drop/{auto.token} -o limpio.{auto.target_format}
              </div>

              <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                <span className="text-slate-500">
                  Formato: <strong className="text-slate-300">{auto.target_format?.toUpperCase()}</strong>
                </span>

                <div className="flex items-center space-x-1.5">
                  <button
                    data-testid={`inspect-webhook-${auto.id}`}
                    onClick={async () => {
                      setInspectorOpen(true);
                      setLoadingInspector(true);
                      try {
                        const res = await axios.get(`${BACKEND_URL}/api/automations/${auto.id}/executions`, { withCredentials: true });
                        setInspectorData(res.data);
                      } catch (err) {
                        alert("Error al cargar historial operacional del webhook.");
                      } finally {
                        setLoadingInspector(false);
                      }
                    }}
                    className="px-2.5 py-1 rounded-md text-xs font-semibold bg-[#3B82F6]/15 hover:bg-[#3B82F6]/25 text-[#38BDF8] border border-[#3B82F6]/30 flex items-center space-x-1 transition-all"
                  >
                    <Activity className="w-3.5 h-3.5" />
                    <span>Inspeccionar</span>
                  </button>

                  <button
                    data-testid={`delete-webhook-${auto.id}`}
                    onClick={() => handleDelete(auto.id)}
                    className="p-1.5 text-slate-400 hover:text-red-400 rounded transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* New Webhook Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-sm font-bold dark:text-white text-slate-900">
                Crear Webhook Drop de Normalización
              </h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateAutomation} className="space-y-3.5">
              <div>
                <label className="text-slate-400 font-medium block mb-1">Nombre del Webhook</label>
                <input
                  type="text"
                  required
                  data-testid="input-automation-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="ej. ERP Ventas Diario Zapier"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white focus:outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="text-slate-400 font-medium block mb-1">Receta a Ejecutar</label>
                <select
                  data-testid="select-automation-recipe"
                  value={recipeId}
                  onChange={(e) => setRecipeId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white focus:outline-none focus:border-[#38BDF8]"
                >
                  {recipes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-slate-400 font-medium block mb-1">Formato de Salida</label>
                <select
                  data-testid="select-automation-format"
                  value={targetFormat}
                  onChange={(e) => setTargetFormat(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white focus:outline-none focus:border-[#38BDF8]"
                >
                  <option value="xlsx">Excel (.xlsx)</option>
                  <option value="csv">CSV (.csv)</option>
                </select>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  data-testid="save-automation-btn"
                  className="px-4 py-1.5 rounded-lg font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white"
                >
                  Crear Endpoint
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Webhook Execution Inspector Drawer / Modal */}
      {inspectorOpen && (
        <div
          data-testid="webhook-inspector-overlay"
          className="fixed inset-0 z-50 flex items-center justify-end p-0 bg-black/60 backdrop-blur-sm"
        >
          <div
            data-testid="webhook-inspector-drawer"
            className="w-full max-w-xl h-full border-l border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl flex flex-col justify-between overflow-y-auto space-y-4"
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Activity className="w-5 h-5 text-[#38BDF8]" />
                  <div>
                    <h3 className="text-base font-bold dark:text-white text-slate-900">
                      Inspector de Ejecuciones Webhook
                    </h3>
                    <p className="text-xs text-slate-400">
                      {inspectorData?.webhook_name} (Receta: {inspectorData?.recipe_name})
                    </p>
                  </div>
                </div>
                <button
                  data-testid="close-inspector-btn"
                  onClick={() => setInspectorOpen(false)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  ✕
                </button>
              </div>

              {loadingInspector ? (
                <div className="py-12 text-center text-xs text-[#38BDF8] flex items-center justify-center space-y-2">
                  <span>Cargando registros operacionales...</span>
                </div>
              ) : inspectorData?.executions?.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-500">
                  No hay ejecuciones registradas todavía para este webhook.
                </div>
              ) : (
                <div className="space-y-3">
                  {inspectorData?.executions?.map((ex, idx) => (
                    <div
                      key={idx}
                      data-testid={`inspector-execution-card-${ex.execution_id}`}
                      className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0E1525] bg-slate-50 space-y-2.5 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[#38BDF8] text-[11px] truncate max-w-[280px]">
                          {ex.file_name}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          {ex.status?.toUpperCase()} ({ex.duration_ms} ms)
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 font-sans">
                        <div>
                          <span>Filas In/Out: </span>
                          <strong className="text-slate-200">{ex.rows_in} → {ex.rows_out}</strong>
                        </div>
                        <div>
                          <span>HMAC: </span>
                          <span className="text-emerald-400 font-semibold">{ex.hmac_status}</span>
                        </div>
                        <div>
                          <span>Anti-Replay: </span>
                          <span className="text-emerald-400 font-semibold">{ex.anti_replay_status}</span>
                        </div>
                        <div>
                          <span>Compatibilidad: </span>
                          <span className="text-[#38BDF8] font-semibold">{ex.schema_compatibility}</span>
                        </div>
                      </div>

                      {/* Applied Aliases audit */}
                      {ex.applied_aliases && Object.keys(ex.applied_aliases).length > 0 && (
                        <div className="p-2 rounded bg-slate-100 dark:bg-[#080D18] text-[11px] text-slate-300 font-sans">
                          <span className="text-slate-400 block text-[10px]">Aliases resueltos:</span>
                          {Object.entries(ex.applied_aliases).map(([orig, canon], aIdx) => (
                            <span key={aIdx} className="inline-block mr-2 text-[#38BDF8]">
                              {orig} → <strong>{canon}</strong>
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Drift details */}
                      {ex.drift_detected && ex.drift_detected.length > 0 && (
                        <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300 font-sans">
                          <span className="font-semibold block text-[10px]">Advertencias de drift:</span>
                          <ul className="list-disc pl-4 space-y-0.5">
                            {ex.drift_detected.map((d, dIdx) => (
                              <li key={dIdx}>{d}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div className="text-[10px] text-slate-500 flex justify-between items-center pt-1 border-t border-slate-200 dark:border-slate-800">
                        <span>ID: {ex.execution_id?.slice(0, 12)}...</span>
                        <span>{new Date(ex.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
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
