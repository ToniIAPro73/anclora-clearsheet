import React, { useState, useEffect } from "react";
import { 
  Cloud, Plus, RefreshCw, Trash2, CheckCircle2, AlertTriangle, 
  Folder, Play, ArrowRight, ShieldCheck, Database, FileSpreadsheet,
  ExternalLink, Key, Lock, Check, Loader2, List
} from "lucide-react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function ConnectorsView({ t, openAuthModal }) {
  const [connections, setConnections] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("connections"); // connections | pipeline

  // Modal create/edit connection
  const [showModal, setShowModal] = useState(false);
  const [connName, setConnName] = useState("");
  const [bucketName, setBucketName] = useState("");
  const [accessKeyId, setAccessKeyId] = useState("");
  const [secretAccessKey, setSecretAccessKey] = useState("");
  const [regionName, setRegionName] = useState("us-east-1");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [testingConn, setTestingConn] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [savingConn, setSavingConn] = useState(false);
  const [formError, setFormError] = useState(null);

  // Object browser state
  const [browsingConn, setBrowsingConn] = useState(null);
  const [remoteObjects, setRemoteObjects] = useState([]);
  const [loadingObjects, setLoadingObjects] = useState(false);
  const [objectPrefix, setObjectPrefix] = useState("");

  // Pipeline Execution state
  const [selectedSourceConn, setSelectedSourceConn] = useState("");
  const [selectedSourceKey, setSelectedSourceKey] = useState("");
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [selectedTargetConn, setSelectedTargetConn] = useState("");
  const [targetPathInput, setTargetPathInput] = useState("");
  const [pipelineOutputFormat, setPipelineOutputFormat] = useState("csv");
  const [executingPipeline, setExecutingPipeline] = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [pipelineError, setPipelineError] = useState(null);

  useEffect(() => {
    fetchConnections();
    fetchRecipes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchConnections = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${BACKEND_URL}/api/connectors`, { withCredentials: true });
      setConnections(res.data || []);
      if (res.data?.length > 0 && !selectedSourceConn) {
        setSelectedSourceConn(res.data[0].id);
        setSelectedTargetConn(res.data[0].id);
      }
    } catch (err) {
      console.error("Error fetching connections:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRecipes = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/recipes`, { withCredentials: true });
      setRecipes(res.data || []);
      if (res.data?.length > 0 && !selectedRecipeId) {
        setSelectedRecipeId(res.data[0].id);
      }
    } catch (err) {
      console.error("Error fetching recipes:", err);
    }
  };

  const handleTestUnsaved = async () => {
    if (!bucketName || !accessKeyId || !secretAccessKey) {
      setFormError("Por favor completa el nombre del bucket, Access Key y Secret Key.");
      return;
    }
    setTestingConn(true);
    setTestResult(null);
    setFormError(null);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/connectors/test`, {
        provider_type: "s3_compatible",
        s3_config: {
          bucket_name: bucketName,
          access_key_id: accessKeyId,
          secret_access_key: secretAccessKey,
          region_name: regionName,
          endpoint_url: endpointUrl || null
        }
      });
      setTestResult(res.data);
    } catch (err) {
      setTestResult({
        success: false,
        message: err.response?.data?.detail || "Fallo en la prueba de conexión."
      });
    } finally {
      setTestingConn(false);
    }
  };

  const handleSaveConnection = async (e) => {
    e.preventDefault();
    if (!connName.trim() || !bucketName.trim() || !accessKeyId.trim() || !secretAccessKey.trim()) {
      setFormError("Todos los campos obligatorios deben completarse.");
      return;
    }

    setSavingConn(true);
    setFormError(null);
    try {
      await axios.post(`${BACKEND_URL}/api/connectors`, {
        name: connName.trim(),
        provider_type: "s3_compatible",
        s3_config: {
          bucket_name: bucketName.trim(),
          access_key_id: accessKeyId.trim(),
          secret_access_key: secretAccessKey.trim(),
          region_name: regionName.trim(),
          endpoint_url: endpointUrl.trim() || null
        }
      }, { withCredentials: true });

      setShowModal(false);
      resetForm();
      fetchConnections();
    } catch (err) {
      setFormError(err.response?.data?.detail || "Error guardando el conector.");
    } finally {
      setSavingConn(false);
    }
  };

  const resetForm = () => {
    setConnName("");
    setBucketName("");
    setAccessKeyId("");
    setSecretAccessKey("");
    setRegionName("us-east-1");
    setEndpointUrl("");
    setTestResult(null);
    setFormError(null);
  };

  const handleDeleteConnection = async (connId) => {
    if (!window.confirm("¿Seguro que deseas eliminar este conector de almacenamiento?")) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/connectors/${connId}`, { withCredentials: true });
      fetchConnections();
      if (browsingConn?.id === connId) {
        setBrowsingConn(null);
      }
    } catch (err) {
      alert("Error eliminando conector.");
    }
  };

  const handleRetestSaved = async (connId) => {
    try {
      const res = await axios.post(`${BACKEND_URL}/api/connectors/${connId}/test`, {}, { withCredentials: true });
      fetchConnections();
      alert(res.data.success ? "Conexión exitosa" : `Fallo: ${res.data.message}`);
    } catch (err) {
      alert("Error probando conexión.");
    }
  };

  const handleOpenBrowser = async (conn) => {
    setBrowsingConn(conn);
    setLoadingObjects(true);
    setRemoteObjects([]);
    try {
      const res = await axios.get(`${BACKEND_URL}/api/connectors/${conn.id}/objects`, {
        params: { prefix: objectPrefix },
        withCredentials: true
      });
      setRemoteObjects(res.data.objects || []);
    } catch (err) {
      alert(err.response?.data?.detail || "Error listando objetos.");
    } finally {
      setLoadingObjects(false);
    }
  };

  const handleExecutePipeline = async (e) => {
    e.preventDefault();
    if (!selectedSourceConn || !selectedSourceKey || !selectedRecipeId) {
      setPipelineError("Debes seleccionar una conexión origen, un objeto S3 y una receta.");
      return;
    }

    setExecutingPipeline(true);
    setPipelineResult(null);
    setPipelineError(null);

    try {
      const res = await axios.post(`${BACKEND_URL}/api/connectors/execute-pipeline`, {
        source_connection_id: selectedSourceConn,
        source_key: selectedSourceKey,
        recipe_id: selectedRecipeId,
        target_connection_id: selectedTargetConn || selectedSourceConn,
        target_key: targetPathInput.trim() || null,
        output_format: pipelineOutputFormat
      }, { withCredentials: true });

      setPipelineResult(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || "Error en la ejecución del pipeline Cloud.";
      setPipelineError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setExecutingPipeline(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header & Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold dark:text-white text-slate-900 flex items-center gap-2">
            <Cloud className="w-5 h-5 text-[#38BDF8]" />
            <span>Conectores Cloud (Source / Target S3)</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Conecta tus propios buckets S3-compatible (AWS, MinIO, Wasabi, Cloudflare R2) para importar y exportar datos limpios de forma directa y determinista.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            data-testid="btn-open-create-connector"
            onClick={() => {
              resetForm();
              setShowModal(true);
            }}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white flex items-center space-x-1.5 shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Nuevo Conector S3</span>
          </button>
        </div>
      </div>

      {/* Navigation tabs between Connections list and Pipeline Execution */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 space-x-4">
        <button
          onClick={() => setActiveTab("connections")}
          className={`pb-2 text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
            activeTab === "connections"
              ? "border-b-2 border-[#38BDF8] text-[#38BDF8]"
              : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Conexiones Guardadas ({connections.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("pipeline")}
          className={`pb-2 text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
            activeTab === "pipeline"
              ? "border-b-2 border-[#38BDF8] text-[#38BDF8]"
              : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Play className="w-4 h-4" />
          <span>Ejecutor Pipeline Cloud (S3 → Receta → S3)</span>
        </button>
      </div>

      {/* Tab 1: Connections Management */}
      {activeTab === "connections" && (
        <div className="space-y-4">
          {loading ? (
            <div className="py-12 flex justify-center items-center">
              <Loader2 className="w-6 h-6 text-[#38BDF8] animate-spin" />
            </div>
          ) : connections.length === 0 ? (
            <div 
              data-testid="no-connectors-notice"
              className="p-8 text-center rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white text-xs text-slate-400 space-y-2"
            >
              <Cloud className="w-8 h-8 text-slate-500 mx-auto" />
              <p className="font-semibold text-slate-300">No tienes conectores externos configurados.</p>
              <p>Añade un bucket S3-compatible propio para procesar datasets remotos sin subirlos manualmente por la UI.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {connections.map((conn) => (
                <div
                  key={conn.id}
                  data-testid={`connector-card-${conn.id}`}
                  className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm flex flex-col justify-between space-y-3"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/30">
                        {conn.provider_type}
                      </span>
                      <span className={`text-[10px] font-semibold flex items-center space-x-1 ${
                        conn.last_test_status === "success" ? "text-emerald-400" : "text-amber-400"
                      }`}>
                        {conn.last_test_status === "success" ? (
                          <CheckCircle2 className="w-3 h-3 inline" />
                        ) : (
                          <AlertTriangle className="w-3 h-3 inline" />
                        )}
                        <span>{conn.last_test_status === "success" ? "Verificado" : "No verificado"}</span>
                      </span>
                    </div>

                    <h4 className="text-sm font-bold dark:text-white text-slate-900 truncate">
                      {conn.name}
                    </h4>

                    <div className="text-xs text-slate-400 space-y-0.5">
                      <p className="truncate">Bucket: <span className="font-mono text-slate-200">{conn.config_preview?.bucket_name}</span></p>
                      <p className="truncate">Región: <span className="text-slate-200">{conn.config_preview?.region_name}</span></p>
                      <p className="truncate">Key ID: <span className="font-mono text-slate-300">{conn.config_preview?.access_key_preview}</span></p>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-1.5">
                      <button
                        data-testid={`btn-browse-objects-${conn.id}`}
                        onClick={() => handleOpenBrowser(conn)}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs flex items-center space-x-1"
                        title="Explorar Objetos"
                      >
                        <Folder className="w-3.5 h-3.5 text-[#38BDF8]" />
                        <span>Explorar</span>
                      </button>

                      <button
                        onClick={() => handleRetestSaved(conn.id)}
                        className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
                        title="Probar Conexión"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <button
                      data-testid={`btn-delete-connector-${conn.id}`}
                      onClick={() => handleDeleteConnection(conn.id)}
                      className="p-1.5 rounded hover:bg-red-500/10 text-slate-400 hover:text-red-400"
                      title="Eliminar Conector"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Object Browser Drawer */}
          {browsingConn && (
            <div className="p-4 rounded-xl border border-slate-700 dark:bg-[#080D18] bg-slate-50 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-700/60 pb-2">
                <div className="flex items-center space-x-2">
                  <Folder className="w-4 h-4 text-[#38BDF8]" />
                  <span className="font-bold text-xs dark:text-white text-slate-900">
                    Objetos en bucket '{browsingConn.config_preview?.bucket_name}'
                  </span>
                </div>
                <button
                  onClick={() => setBrowsingConn(null)}
                  className="text-xs text-slate-400 hover:text-white"
                >
                  Cerrar
                </button>
              </div>

              {loadingObjects ? (
                <div className="py-6 flex justify-center">
                  <Loader2 className="w-5 h-5 text-[#38BDF8] animate-spin" />
                </div>
              ) : remoteObjects.length === 0 ? (
                <p className="text-xs text-slate-400 py-4 text-center">
                  No se encontraron objetos en este bucket con el prefijo especificado.
                </p>
              ) : (
                <div className="divide-y divide-slate-800 text-xs max-h-60 overflow-y-auto">
                  {remoteObjects.map((obj) => (
                    <div key={obj.key} className="py-2 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <FileSpreadsheet className="w-3.5 h-3.5 text-[#38BDF8]" />
                        <span className="font-mono text-slate-200">{obj.key}</span>
                      </div>
                      <div className="flex items-center space-x-3 text-slate-400">
                        <span>{(obj.size_bytes / 1024).toFixed(1)} KB</span>
                        <button
                          onClick={() => {
                            setSelectedSourceConn(browsingConn.id);
                            setSelectedSourceKey(obj.key);
                            setActiveTab("pipeline");
                          }}
                          className="px-2 py-0.5 rounded bg-[#3B82F6]/20 text-[#38BDF8] hover:bg-[#3B82F6]/30 text-[11px]"
                        >
                          Usar como Origen
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Pipeline Execution */}
      {activeTab === "pipeline" && (
        <form onSubmit={handleExecutePipeline} className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white space-y-4">
          <div>
            <h3 className="text-base font-bold dark:text-white text-slate-900 flex items-center gap-2">
              <Play className="w-4 h-4 text-[#38BDF8]" />
              <span>Ejecución de Pipeline Cloud a Cloud</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Lee el archivo crudo desde el S3 origen, aplica tu receta determinista y escribe el resultado directamente en el S3 destino sin pasar por tu ordenador.
            </p>
          </div>

          {pipelineError && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
              {pipelineError}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Source Config */}
            <div className="p-4 rounded-xl border border-slate-800 bg-[#0E1525] space-y-3">
              <span className="text-xs font-bold text-[#38BDF8] block">1. Origen Cloud (Source)</span>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Conector S3 Origen</label>
                <select
                  data-testid="select-pipeline-source-conn"
                  value={selectedSourceConn}
                  onChange={(e) => setSelectedSourceConn(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-xs text-white"
                >
                  {connections.map((c) => (
                    <option key={c.id} value={c.id}>{c.name} ({c.config_preview?.bucket_name})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Clave de Objeto Origen (S3 Key)</label>
                <input
                  type="text"
                  data-testid="input-pipeline-source-key"
                  value={selectedSourceKey}
                  onChange={(e) => setSelectedSourceKey(e.target.value)}
                  placeholder="ej. raw/ventas_2026.csv"
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-xs text-white"
                />
              </div>
            </div>

            {/* Target Config */}
            <div className="p-4 rounded-xl border border-slate-800 bg-[#0E1525] space-y-3">
              <span className="text-xs font-bold text-emerald-400 block">2. Destino Cloud (Target)</span>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Conector S3 Destino</label>
                <select
                  data-testid="select-pipeline-target-conn"
                  value={selectedTargetConn}
                  onChange={(e) => setSelectedTargetConn(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-xs text-white"
                >
                  {connections.map((c) => (
                    <option key={c.id} value={c.id}>{c.name} ({c.config_preview?.bucket_name})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Clave de Destino (Opcional)</label>
                <input
                  type="text"
                  data-testid="input-pipeline-target-key"
                  value={targetPathInput}
                  onChange={(e) => setTargetPathInput(e.target.value)}
                  placeholder="ej. normalized/ventas_2026_clean.csv"
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-xs text-white"
                />
              </div>
            </div>
          </div>

          {/* Recipe Selection */}
          <div className="p-4 rounded-xl border border-slate-800 bg-[#0E1525] space-y-3">
            <span className="text-xs font-bold text-slate-200 block">3. Receta Determinista a Aplicar</span>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Receta</label>
                <select
                  data-testid="select-pipeline-recipe"
                  value={selectedRecipeId}
                  onChange={(e) => setSelectedRecipeId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-xs text-white"
                >
                  {recipes.map((r) => (
                    <option key={r.id} value={r.id}>{r.name} (v{r.recipe_version || "1.0"})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Formato de Salida</label>
                <select
                  value={pipelineOutputFormat}
                  onChange={(e) => setPipelineOutputFormat(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#080D18] text-xs text-white"
                >
                  <option value="csv">CSV (.csv)</option>
                  <option value="xlsx">Excel (.xlsx)</option>
                </select>
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={executingPipeline}
              data-testid="btn-execute-pipeline-submit"
              className="px-5 py-2.5 rounded-xl font-semibold bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-50 text-white text-xs flex items-center space-x-1.5 shadow-md transition-all"
            >
              {executingPipeline ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{executingPipeline ? "Procesando en Cloud..." : "Ejecutar Pipeline S3"}</span>
            </button>
          </div>

          {/* Pipeline Execution Result Banner */}
          {pipelineResult && (
            <div data-testid="pipeline-result-banner" className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 space-y-2 text-xs">
              <div className="flex items-center space-x-2 text-emerald-400 font-bold">
                <CheckCircle2 className="w-4 h-4" />
                <span>Pipeline Cloud ejecutado con éxito</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-slate-300">
                <div>
                  <span className="text-[10px] text-slate-400 block">Filas Procesadas:</span>
                  <span className="font-semibold">{pipelineResult.rows_in} → {pipelineResult.rows_out}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Cambios Deterministas:</span>
                  <span className="font-semibold text-emerald-400">{pipelineResult.changes_count}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Destino ETag:</span>
                  <span className="font-mono text-[10px] truncate block">{pipelineResult.target?.etag || "OK"}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block">Duración:</span>
                  <span className="font-semibold">{pipelineResult.duration_ms} ms</span>
                </div>
              </div>
            </div>
          )}
        </form>
      )}

      {/* Modal: New Connection */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Cloud className="w-5 h-5 text-[#38BDF8]" />
                <h3 className="text-base font-bold dark:text-white text-slate-900">
                  Configurar Conector S3-Compatible
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

            <form onSubmit={handleSaveConnection} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-300 font-medium block mb-1">Nombre descriptivo de la conexión</label>
                <input
                  type="text"
                  data-testid="input-conn-name"
                  value={connName}
                  onChange={(e) => setConnName(e.target.value)}
                  placeholder="ej. AWS S3 Ventas Europa"
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-300 font-medium block mb-1">Nombre del Bucket</label>
                  <input
                    type="text"
                    data-testid="input-bucket-name"
                    value={bucketName}
                    onChange={(e) => setBucketName(e.target.value)}
                    placeholder="mi-bucket-lake"
                    className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white"
                    required
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-medium block mb-1">Región</label>
                  <input
                    type="text"
                    data-testid="input-region-name"
                    value={regionName}
                    onChange={(e) => setRegionName(e.target.value)}
                    placeholder="us-east-1"
                    className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 font-medium block mb-1">Access Key ID</label>
                <input
                  type="text"
                  data-testid="input-access-key"
                  value={accessKeyId}
                  onChange={(e) => setAccessKeyId(e.target.value)}
                  placeholder="AKIA..."
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white font-mono"
                  required
                />
              </div>

              <div>
                <label className="text-slate-300 font-medium block mb-1">Secret Access Key</label>
                <input
                  type="password"
                  data-testid="input-secret-key"
                  value={secretAccessKey}
                  onChange={(e) => setSecretAccessKey(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white font-mono"
                  required
                />
              </div>

              <div>
                <label className="text-slate-300 font-medium block mb-1">
                  Endpoint URL Personalizado (Opcional - MinIO / Cloudflare R2 / Wasabi)
                </label>
                <input
                  type="url"
                  data-testid="input-endpoint-url"
                  value={endpointUrl}
                  onChange={(e) => setEndpointUrl(e.target.value)}
                  placeholder="https://s3.eu-central-1.wasabisys.com"
                  className="w-full px-3 py-2 rounded-lg border border-slate-700 bg-[#0E1525] text-white"
                />
                <span className="text-[10px] text-slate-500 mt-0.5 block">
                  Protegido contra SSRF: Solo se permiten endpoints públicos HTTPS autorizados.
                </span>
              </div>

              {/* Test feedback */}
              {testResult && (
                <div className={`p-2.5 rounded-lg border text-xs flex items-center space-x-2 ${
                  testResult.success
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                    : "bg-red-500/10 border-red-500/30 text-red-400"
                }`}>
                  {testResult.success ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
                  <span>{testResult.message}</span>
                </div>
              )}

              <div className="flex items-center justify-between pt-3 border-t border-slate-700">
                <button
                  type="button"
                  data-testid="btn-test-connection"
                  onClick={handleTestUnsaved}
                  disabled={testingConn}
                  className="px-3.5 py-1.5 rounded-lg border border-slate-700 hover:border-[#38BDF8] text-slate-300 hover:text-white flex items-center space-x-1.5"
                >
                  {testingConn ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5 text-[#38BDF8]" />}
                  <span>{testingConn ? "Probando..." : "Probar Conexión"}</span>
                </button>

                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    data-testid="btn-save-connector-submit"
                    disabled={savingConn}
                    className="px-4 py-1.5 rounded-lg font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white"
                  >
                    {savingConn ? "Guardando..." : "Guardar Conector"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
