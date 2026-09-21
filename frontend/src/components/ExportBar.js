import React, { useState } from "react";
import { Download, FileCode, Code2, BookmarkPlus, Check, Copy } from "lucide-react";
import axios from "axios";
import { useAuth } from "../context/AuthContext";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function ExportBar({
  fileId,
  rules,
  recipeYaml,
  pythonScript,
  structureFingerprint,
  t,
  openAuthModal,
  onRecipeSaved
}) {
  const { user } = useAuth();
  const [modalType, setModalType] = useState(null); // "yaml" | "python" | "save" | null
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [recipeName, setRecipeName] = useState("");
  const [savingRecipe, setSavingRecipe] = useState(false);

  const handleDownloadFile = async (format) => {
    setDownloading(true);
    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/files/export?format=${format}`,
        { file_id: fileId, rules: rules },
        { responseType: "blob", withCredentials: true }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `cleansheet_resultado.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      alert("Error al descargar archivo normalizado.");
    } finally {
      setDownloading(false);
    }
  };

  const downloadTextFile = (content, filename, type) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveRecipe = async () => {
    if (!user) {
      openAuthModal();
      return;
    }
    if (!recipeName.trim()) {
      alert("Por favor ingresa un nombre para la receta.");
      return;
    }

    setSavingRecipe(true);
    try {
      await axios.post(
        `${BACKEND_URL}/api/recipes`,
        {
          name: recipeName.trim(),
          recipe_yaml: recipeYaml,
          structure_fingerprint: structureFingerprint,
          source_format: "xlsx"
        },
        { withCredentials: true }
      );
      setModalType(null);
      setRecipeName("");
      if (onRecipeSaved) onRecipeSaved();
      alert("¡Receta guardada exitosamente en tu cuenta!");
    } catch (e) {
      alert("Error al guardar la receta.");
    } finally {
      setSavingRecipe(false);
    }
  };

  return (
    <>
      <div
        data-testid="export-bar-container"
        className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4"
      >
        <div>
          <h4 className="text-base font-bold dark:text-white text-slate-900">{t.export.title}</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Descarga los datos 100% procesados o la receta reproducible sin depender de CleanSheet.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Download Clean Excel */}
          <button
            data-testid="download-excel-btn"
            onClick={() => handleDownloadFile("xlsx")}
            disabled={downloading}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white shadow-sm shadow-[#3B82F6]/30 transition-all flex items-center space-x-1.5 focus:ring-2 focus:ring-[#38BDF8]"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{t.export.download_excel}</span>
          </button>

          {/* Download Clean CSV */}
          <button
            data-testid="download-csv-btn"
            onClick={() => handleDownloadFile("csv")}
            disabled={downloading}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 transition-all flex items-center space-x-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{t.export.download_csv}</span>
          </button>

          {/* View / Download YAML Recipe */}
          <button
            data-testid="view-recipe-yaml-btn"
            onClick={() => setModalType("yaml")}
            className="px-3 py-2 rounded-xl text-xs font-semibold border border-[#3B82F6]/40 hover:border-[#38BDF8] text-[#38BDF8] dark:bg-[#0E1525] bg-sky-50/50 hover:bg-[#3B82F6]/10 transition-all flex items-center space-x-1.5"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>YAML</span>
          </button>

          {/* View / Download Python Script */}
          <button
            data-testid="view-python-script-btn"
            onClick={() => setModalType("python")}
            className="px-3 py-2 rounded-xl text-xs font-semibold border border-[#3B82F6]/40 hover:border-[#38BDF8] text-[#38BDF8] dark:bg-[#0E1525] bg-sky-50/50 hover:bg-[#3B82F6]/10 transition-all flex items-center space-x-1.5"
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>Python</span>
          </button>

          {/* Save Recipe to Account */}
          <button
            data-testid="save-recipe-account-btn"
            onClick={() => {
              if (!user) openAuthModal();
              else setModalType("save");
            }}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition-all flex items-center space-x-1.5"
          >
            <BookmarkPlus className="w-3.5 h-3.5" />
            <span>{t.export.save_recipe_btn}</span>
          </button>
        </div>
      </div>

      {/* Code Modal Dialog (YAML or Python) */}
      {modalType && (
        <div
          data-testid="code-preview-modal"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        >
          <div className="w-full max-w-2xl rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="text-base font-bold dark:text-white text-slate-900">
                {modalType === "yaml"
                  ? t.export.recipe_modal_title
                  : modalType === "python"
                  ? t.export.python_modal_title
                  : "Guardar Receta en tu Cuenta"}
              </h3>
              <button
                data-testid="modal-close-btn"
                onClick={() => setModalType(null)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded"
              >
                ✕
              </button>
            </div>

            {modalType === "save" ? (
              <div className="space-y-4 py-2">
                <p className="text-xs text-slate-400">
                  Asigna un nombre descriptivo a esta receta determinista para aplicarla posteriormente
                  a nuevos archivos equivalentes.
                </p>
                <div>
                  <label className="text-xs font-medium text-slate-300 block mb-1">Nombre de la Receta</label>
                  <input
                    type="text"
                    data-testid="input-recipe-name"
                    value={recipeName}
                    onChange={(e) => setRecipeName(e.target.value)}
                    placeholder="ej. ERP Ventas Mensual SAGE"
                    className="w-full px-3 py-2 rounded-lg border border-slate-700 dark:bg-[#0E1525] text-xs text-white focus:outline-none focus:border-[#38BDF8]"
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    onClick={() => setModalType(null)}
                    className="px-3 py-1.5 rounded-lg text-xs border border-slate-700 text-slate-400 hover:text-white"
                  >
                    Cancelar
                  </button>
                  <button
                    data-testid="confirm-save-recipe-btn"
                    onClick={handleSaveRecipe}
                    disabled={savingRecipe}
                    className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white"
                  >
                    {savingRecipe ? "Guardando..." : "Guardar Receta"}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="relative">
                  <pre
                    data-testid="modal-code-content"
                    className="p-4 rounded-xl border border-slate-800 bg-[#080D18] text-[#38BDF8] text-xs font-mono max-h-[350px] overflow-auto select-all leading-relaxed"
                  >
                    {modalType === "yaml" ? recipeYaml : pythonScript}
                  </pre>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    data-testid="modal-copy-btn"
                    onClick={() => copyToClipboard(modalType === "yaml" ? recipeYaml : pythonScript)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-700 hover:border-[#38BDF8] text-slate-300 hover:text-white flex items-center space-x-1.5"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied ? t.export.copied : t.export.copy_clipboard}</span>
                  </button>

                  <div className="flex items-center space-x-2">
                    <button
                      data-testid="modal-download-raw-btn"
                      onClick={() => {
                        if (modalType === "yaml") {
                          downloadTextFile(recipeYaml, "recipe.yaml", "text/yaml");
                        } else {
                          downloadTextFile(pythonScript, "clean_data.py", "text/x-python");
                        }
                      }}
                      className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white flex items-center space-x-1.5"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>{modalType === "yaml" ? "Descargar .yaml" : "Descargar .py"}</span>
                    </button>
                    <button
                      onClick={() => setModalType(null)}
                      className="px-3 py-1.5 rounded-lg text-xs border border-slate-700 text-slate-400 hover:text-white"
                    >
                      {t.export.close}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
