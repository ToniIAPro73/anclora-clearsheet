import React, { useState, useEffect } from "react";
import { BookOpen, Play, Trash2, Download, AlertTriangle, CheckCircle2, UploadCloud, Loader2, Settings, Plus, Tag } from "lucide-react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function RecipesView({ t, onSelectRecipeForReapplication }) {
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRecipe, setSelectedRecipe] = useState(null);
  const [candidateFile, setCandidateFile] = useState(null);
  const [compatibility, setCompatibility] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [executing, setExecuting] = useState(false);

  // Alias Editor Drawer state
  const [aliasModalOpen, setAliasModalOpen] = useState(false);
  const [editingRecipe, setEditingRecipe] = useState(null);
  const [canonicalCols, setCanonicalCols] = useState([]);
  const [aliasesMap, setAliasesMap] = useState({});
  const [selectedCanonical, setSelectedCanonical] = useState("");
  const [newAliasInput, setNewAliasInput] = useState("");
  const [aliasError, setAliasError] = useState(null);
  const [savingAlias, setSavingAlias] = useState(false);

  useEffect(() => {
    fetchRecipes();
  }, []);

  const fetchRecipes = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/recipes`, { withCredentials: true });
      setRecipes(res.data || []);
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const openAliasEditor = async (recipe) => {
    setEditingRecipe(recipe);
    setAliasModalOpen(true);
    setAliasError(null);
    try {
      const res = await axios.get(`${BACKEND_URL}/api/recipes/${recipe.id}/aliases`, { withCredentials: true });
      setCanonicalCols(res.data.canonical_columns || []);
      setAliasesMap(res.data.aliases || {});
      if (res.data.canonical_columns?.length > 0) {
        setSelectedCanonical(res.data.canonical_columns[0]);
      }
    } catch (err) {
      setAliasError("No se pudieron cargar los aliases de la receta.");
    }
  };

  const handleAddAlias = async (e) => {
    e.preventDefault();
    if (!newAliasInput.trim() || !selectedCanonical) return;
    setSavingAlias(true);
    setAliasError(null);

    // Front-end immediate validations
    if (newAliasInput.trim().toLowerCase() === selectedCanonical.toLowerCase()) {
      setAliasError(`La columna canónica '${selectedCanonical}' no puede ser su propio alias.`);
      setSavingAlias(false);
      return;
    }

    try {
      const res = await axios.post(
        `${BACKEND_URL}/api/recipes/${editingRecipe.id}/aliases`,
        { canonical_column: selectedCanonical, alias: newAliasInput.trim() },
        { withCredentials: true }
      );
      setAliasesMap(res.data.aliases);
      setNewAliasInput("");
      fetchRecipes();
    } catch (err) {
      setAliasError(err.response?.data?.detail || "Error al añadir alias.");
    } finally {
      setSavingAlias(false);
    }
  };

  const handleDelete = async (recipeId) => {
    if (!window.confirm(t.recipes_view.delete_confirm)) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/recipes/${recipeId}`, { withCredentials: true });
      setRecipes(recipes.filter((r) => r.id !== recipeId));
    } catch (e) {
      alert("Error al eliminar la receta.");
    }
  };

  const handleRemoveAlias = async (canonical, alias) => {
    try {
      const res = await axios.delete(
        `${BACKEND_URL}/api/recipes/${editingRecipe.id}/aliases`,
        {
          data: { canonical_column: canonical, alias: alias },
          withCredentials: true
        }
      );
      setAliasesMap(res.data.aliases);
      fetchRecipes();
    } catch (err) {
      alert("Error al eliminar alias.");
    }
  };

  const handleUploadCandidate = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setVerifying(true);
    setCompatibility(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const uploadRes = await axios.post(`${BACKEND_URL}/api/files/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        withCredentials: true
      });

      const fileId = uploadRes.data.file_id;
      setCandidateFile(uploadRes.data);

      // Validate compatibility with selected recipe
      const compatRes = await axios.post(
        `${BACKEND_URL}/api/recipes/validate-compatibility`,
        {
          recipe_id: selectedRecipe.id,
          file_id: fileId
        },
        { withCredentials: true }
      );
      setCompatibility(compatRes.data);
    } catch (err) {
      alert("Error al validar compatibilidad.");
    } finally {
      setVerifying(false);
    }
  };

  const handleExecuteReapply = async () => {
    if (!candidateFile || !compatibility) return;
    setExecuting(true);
    try {
      const rules = compatibility.proposed_rules;
      const response = await axios.post(
        `${BACKEND_URL}/api/files/export?format=xlsx`,
        { file_id: candidateFile.file_id, rules: rules },
        { responseType: "blob", withCredentials: true }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `reaplicado_${candidateFile.filename}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setSelectedRecipe(null);
      setCandidateFile(null);
      setCompatibility(null);
      alert("¡Archivo procesado y descargado exitosamente con la receta!");
    } catch (e) {
      alert("Error durante la ejecución de la receta.");
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 flex justify-center items-center">
        <Loader2 className="w-8 h-8 text-[#38BDF8] animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold dark:text-white text-slate-900 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[#38BDF8]" />
            <span>{t.recipes_view.title}</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Automatiza la normalización determinista reutilizando tus recetas versionadas.
          </p>
        </div>
      </div>

      {recipes.length === 0 ? (
        <div
          data-testid="recipes-empty-state"
          className="p-12 text-center rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white space-y-3"
        >
          <BookOpen className="w-12 h-12 text-slate-400 mx-auto opacity-50" />
          <h4 className="text-base font-bold dark:text-white text-slate-800">
            {t.recipes_view.empty_title}
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">{t.recipes_view.empty_desc}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {recipes.map((rec) => (
            <div
              key={rec.id}
              data-testid={`recipe-card-${rec.id}`}
              className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm flex flex-col justify-between space-y-3 hover:border-[#3B82F6]/50 transition-all"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/30">
                    v{rec.recipe_version}
                  </span>
                  <code className="text-[10px] text-slate-400 font-mono">
                    {rec.structure_fingerprint?.slice(0, 8)}
                  </code>
                </div>
                <h4 className="text-sm font-bold dark:text-white text-slate-900 mt-2">
                  {rec.name}
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                  {rec.description || "Receta de normalización determinista"}
                </p>
              </div>

              <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                <button
                  data-testid={`btn-reapply-${rec.id}`}
                  onClick={() => setSelectedRecipe(rec)}
                  className="px-3 py-1.5 rounded-lg bg-[#3B82F6] hover:bg-[#2563EB] text-white font-semibold flex items-center space-x-1"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>{t.recipes_view.btn_reapply}</span>
                </button>

                <div className="flex items-center space-x-1">
                  <button
                    data-testid={`btn-aliases-${rec.id}`}
                    onClick={() => openAliasEditor(rec)}
                    title="Editar Aliases de Columnas"
                    className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-400 hover:text-[#38BDF8] transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                  </button>

                  <button
                    data-testid={`btn-delete-${rec.id}`}
                    onClick={() => handleDelete(rec.id)}
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

      {/* Reapplication & Compatibility Validation Modal */}
      {selectedRecipe && (
        <div
          data-testid="reapply-modal"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        >
          <div className="w-full max-w-lg rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-sm font-bold dark:text-white text-slate-900">
                {t.recipes_view.reapply_modal_title} {selectedRecipe.name}
              </h3>
              <button
                onClick={() => {
                  setSelectedRecipe(null);
                  setCandidateFile(null);
                  setCompatibility(null);
                }}
                className="text-slate-400 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400">{t.recipes_view.reapply_instruction}</p>

            {/* Candidate File Upload Input */}
            <div className="p-6 border-2 border-dashed border-slate-700 rounded-xl text-center cursor-pointer hover:border-[#38BDF8]">
              <input
                type="file"
                data-testid="candidate-file-input"
                accept=".xlsx,.csv"
                onChange={handleUploadCandidate}
                className="w-full text-xs text-slate-400 file:mr-4 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#3B82F6]/20 file:text-[#38BDF8] hover:file:bg-[#3B82F6]/30 cursor-pointer"
              />
            </div>

            {verifying && (
              <div className="flex items-center justify-center space-x-2 text-xs text-[#38BDF8] py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>{t.recipes_view.compat_verifying}</span>
              </div>
            )}

            {/* Compatibility Result Evaluation Badge */}
            {compatibility && (
              <div
                data-testid="compatibility-result-box"
                className={`p-3.5 rounded-xl border text-xs space-y-1.5 ${
                  compatibility.compatibility.status === "compatible"
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : compatibility.compatibility.status === "compatible_with_warnings"
                    ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
                    : "border-rose-500/30 bg-rose-500/10 text-rose-400"
                }`}
              >
                <div className="flex items-center space-x-1.5 font-bold">
                  {compatibility.compatibility.status === "compatible" ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : (
                    <AlertTriangle className="w-4 h-4" />
                  )}
                  <span>
                    {compatibility.compatibility.message_es ||
                      compatibility.compatibility.message_en}
                  </span>
                </div>
                <div className="text-[11px] opacity-80">
                  Archivo cargado: {compatibility.filename} (Score:{" "}
                  {compatibility.compatibility.score})
                </div>
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => {
                  setSelectedRecipe(null);
                  setCandidateFile(null);
                  setCompatibility(null);
                }}
                className="px-3 py-1.5 rounded-lg text-xs border border-slate-700 text-slate-400 hover:text-white"
              >
                Cancelar
              </button>
              <button
                data-testid="execute-reapply-confirm-btn"
                disabled={!compatibility || compatibility.compatibility.status === "incompatible" || executing}
                onClick={handleExecuteReapply}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center space-x-1.5"
              >
                {executing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{t.recipes_view.execute_reapply_btn}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Phase 1: Alias Rule Editor Modal / Drawer */}
      {aliasModalOpen && editingRecipe && (
        <div
          data-testid="alias-editor-overlay"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        >
          <div
            data-testid="alias-editor-modal"
            className="w-full max-w-lg rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4 text-xs"
          >
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold dark:text-white text-slate-900 flex items-center gap-1.5">
                  <Tag className="w-4 h-4 text-[#38BDF8]" />
                  <span>Editor de Aliases de Columnas</span>
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Receta: {editingRecipe.name} (v{editingRecipe.recipe_version})
                </p>
              </div>
              <button
                onClick={() => setAliasModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded"
              >
                ✕
              </button>
            </div>

            {aliasError && (
              <div
                data-testid="alias-error-banner"
                className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-xs"
              >
                {aliasError}
              </div>
            )}

            {/* Existing Aliases per Canonical Column */}
            <div className="space-y-3 max-h-[250px] overflow-y-auto pr-1">
              <span className="font-semibold text-slate-400 block text-[11px] uppercase tracking-wider">
                Mapeos de Columnas Canónicas:
              </span>

              {canonicalCols.map((cCol) => {
                const aliases = aliasesMap[cCol] || [];
                return (
                  <div
                    key={cCol}
                    data-testid={`canonical-col-group-${cCol}`}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0E1525] bg-slate-50 space-y-2"
                  >
                    <div className="flex items-center justify-between font-bold text-slate-800 dark:text-slate-200">
                      <span className="font-mono text-[#38BDF8]">{cCol}</span>
                      <span className="text-[10px] text-slate-400 font-sans">
                        {aliases.length} alias configurados
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-1.5">
                      {aliases.length === 0 ? (
                        <span className="text-[11px] text-slate-400 italic">Sin aliases</span>
                      ) : (
                        aliases.map((al) => (
                          <span
                            key={al}
                            data-testid={`alias-chip-${al}`}
                            className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/30 text-[11px]"
                          >
                            <span>{al}</span>
                            <button
                              data-testid={`remove-alias-${al}`}
                              onClick={() => handleRemoveAlias(cCol, al)}
                              className="hover:text-red-400 ml-1 font-bold"
                            >
                              ×
                            </button>
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Add New Alias Form */}
            <form onSubmit={handleAddAlias} className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#080D18] bg-white space-y-3">
              <span className="font-bold text-slate-700 dark:text-slate-300 block">Añadir Nuevo Alias:</span>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Columna Canónica</label>
                  <select
                    data-testid="select-canonical-col"
                    value={selectedCanonical}
                    onChange={(e) => setSelectedCanonical(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white"
                  >
                    {canonicalCols.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Nombre Alternativo (Alias)</label>
                  <input
                    type="text"
                    required
                    data-testid="input-new-alias"
                    value={newAliasInput}
                    onChange={(e) => setNewAliasInput(e.target.value)}
                    placeholder="ej. codigo_cliente"
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="submit"
                  disabled={savingAlias || !newAliasInput.trim()}
                  data-testid="btn-submit-alias"
                  className="px-3.5 py-1.5 rounded-lg font-semibold bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-40 text-white flex items-center space-x-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Añadir Alias a Receta</span>
                </button>
              </div>
            </form>

            <div className="flex justify-end pt-2 border-t border-slate-200 dark:border-slate-800">
              <button
                onClick={() => setAliasModalOpen(false)}
                className="px-4 py-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-white"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
