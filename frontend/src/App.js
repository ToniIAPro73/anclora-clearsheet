import React, { useState, useEffect, useCallback } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { debounce } from "lodash";
import { AuthProvider } from "./context/AuthContext";
import { UIProvider, useUI } from "./context/UIContext";
import { translations } from "./i18n";
import { api } from "./lib/api";

import Header from "./components/Header";
import DropZone from "./components/DropZone";
import AnalysisSummary from "./components/AnalysisSummary";
import RulesPanel from "./components/RulesPanel";
import ComparisonGrid from "./components/ComparisonGrid";
import ExportBar from "./components/ExportBar";
import RecipesView from "./components/RecipesView";
import HistoryView from "./components/HistoryView";
import BatchProcessingView from "./components/BatchProcessingView";
import AutomationsView from "./components/AutomationsView";
import StreamParsingView from "./components/StreamParsingView";
import ConnectorsView from "./components/ConnectorsView";
import SchedulesView from "./components/SchedulesView";
import ProtectedRoute from "./components/ProtectedRoute";
import Landing from "./components/Landing";
import Login from "./components/Login";
import ActivateAccess from "./components/ActivateAccess";

const listUnique = (arr) => Array.from(new Set(arr));

export function CleanSheetApp() {
  const { theme, setTheme, lang, setLang } = useUI();
  const [activeTab, setActiveTab] = useState("clean"); // "clean" | "stream" | "batch" | "automations" | "connectors" | "schedules" | "recipes" | "history"

  // Active File Data & Analysis
  const [currentFile, setCurrentFile] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [originalPreview, setOriginalPreview] = useState(null);
  const [activeRules, setActiveRules] = useState(null);
  const [normalizedPreview, setNormalizedPreview] = useState(null);
  const [recipeYaml, setRecipeYaml] = useState("");
  const [pythonScript, setPythonScript] = useState("");
  const [isRecalculating, setIsRecalculating] = useState(false);

  const t = translations[lang] || translations.es;

  const handleAnalysisComplete = ({ fileInfo, analysisData }) => {
    setCurrentFile(fileInfo);
    setAnalysisData(analysisData.analysis);
    setOriginalPreview(analysisData.original_preview);
    setActiveRules(analysisData.analysis.default_rules);
    setNormalizedPreview(analysisData.normalized_preview);
    setRecipeYaml(analysisData.analysis.recipe_yaml);
    setPythonScript(analysisData.python_script);
  };

  // Debounced preview recalculation (300ms) when rules change
  const recalculatePreview = useCallback((fileId, newRules) => {
    const debouncedFn = debounce(async (fId, rules) => {
      setIsRecalculating(true);
      try {
        const res = await api.post("/files/preview", {
          file_id: fId,
          rules: rules
        });
        if (res.data) {
          setNormalizedPreview(res.data.preview);
          setRecipeYaml(res.data.recipe_yaml);
          setPythonScript(res.data.python_script);
        }
      } catch (err) {
        console.error("Preview recalculation error:", err);
      } finally {
        setIsRecalculating(false);
      }
    }, 300);
    debouncedFn(fileId, newRules);
  }, []);

  const handleRuleChange = (key, value) => {
    const updated = { ...activeRules, [key]: value };
    setActiveRules(updated);
    if (currentFile?.file_id) {
      recalculatePreview(currentFile.file_id, updated);
    }
  };

  return (
    <div
      data-testid="app-root-container"
      className="min-h-screen flex flex-col font-sans transition-colors duration-200 dark:bg-[#080D18] bg-slate-50 text-slate-900 dark:text-slate-100 selection:bg-[#38BDF8]/30 selection:text-white"
    >
      <Header
        t={t}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {activeTab === "clean" && (
          <>
            {/* Hero / Upload Workspace */}
            {!currentFile ? (
              <div className="space-y-6 pt-4 text-center">
                <div className="max-w-2xl mx-auto space-y-2">
                  <h1
                    data-testid="hero-main-title"
                    className="text-3xl sm:text-4xl font-extrabold tracking-tight dark:text-white text-slate-950"
                  >
                    {t.brand_name}
                  </h1>
                  <p className="text-base sm:text-lg text-slate-600 dark:text-slate-400 font-normal">
                    {t.subtitle}
                  </p>
                  <p className="text-xs text-slate-400 dark:text-slate-500 max-w-lg mx-auto">
                    {t.tagline}
                  </p>
                </div>

                <DropZone t={t} onAnalysisComplete={handleAnalysisComplete} />
              </div>
            ) : (
              <div className="space-y-6">
                {/* File Header Bar & Reset Button */}
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-wider text-[#38BDF8]">
                      Archivo en Limpieza
                    </span>
                    <h3 className="text-base font-bold dark:text-white text-slate-900">
                      {currentFile.filename}
                    </h3>
                  </div>

                  <button
                    data-testid="reset-file-btn"
                    onClick={() => {
                      setCurrentFile(null);
                      setAnalysisData(null);
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:border-red-400 text-slate-600 dark:text-slate-400 hover:text-red-400 transition-colors self-start sm:self-auto cursor-pointer"
                  >
                    Cargar otro archivo
                  </button>
                </div>

                {/* Analysis Heuristic Summary with Contextual Drift/Alias Resolution */}
                <AnalysisSummary
                  analysis={analysisData}
                  t={t}
                  onApplyAliasOnce={(candCol, canonicalCol) => {
                    const currentAliases = activeRules?.column_aliases || {};
                    const existing = currentAliases[canonicalCol] || [];
                    handleRuleChange("column_aliases", {
                      ...currentAliases,
                      [canonicalCol]: listUnique([...existing, candCol])
                    });
                  }}
                  onSaveAliasToRecipe={async (candCol, canonicalCol) => {
                    // Persistent versioned update if user has active recipe
                    if (currentFile?.recipe_id) {
                      try {
                        await api.post(`/recipes/${currentFile.recipe_id}/aliases`, {
                          canonical_column: canonicalCol,
                          alias: candCol
                        });
                        alert(`Alias '${candCol}' guardado en la receta de forma versionada.`);
                      } catch (e) {
                        alert("Error al persistir alias en la receta.");
                      }
                    } else {
                      // Apply in memory rules
                      const currentAliases = activeRules?.column_aliases || {};
                      const existing = currentAliases[canonicalCol] || [];
                      handleRuleChange("column_aliases", {
                        ...currentAliases,
                        [canonicalCol]: listUnique([...existing, candCol])
                      });
                      alert(`Alias '${candCol} -> ${canonicalCol}' configurado para esta sesión.`);
                    }
                  }}
                />

                {/* Rules Panel with Live Recalculation */}
                <RulesPanel
                  rules={activeRules}
                  onChangeRule={handleRuleChange}
                  isRecalculating={isRecalculating}
                  analysis={analysisData}
                  t={t}
                />

                {/* Interactive Before / After Comparison Grid */}
                <ComparisonGrid
                  original={originalPreview}
                  normalized={normalizedPreview}
                  t={t}
                />

                {/* Export Bar: Clean Files (XLSX, CSV) + YAML Recipe + Python Script */}
                <ExportBar
                  fileId={currentFile.file_id}
                  rules={activeRules}
                  recipeYaml={recipeYaml}
                  pythonScript={pythonScript}
                  structureFingerprint={analysisData?.structure_fingerprint}
                  t={t}
                  openAuthModal={() => {}}
                  onRecipeSaved={() => setActiveTab("recipes")}
                />
              </div>
            )}
          </>
        )}

        {activeTab === "stream" && (
          <StreamParsingView t={t} />
        )}

        {activeTab === "batch" && (
          <BatchProcessingView t={t} openAuthModal={() => {}} />
        )}

        {activeTab === "automations" && (
          <AutomationsView t={t} openAuthModal={() => {}} />
        )}

        {activeTab === "connectors" && (
          <ConnectorsView t={t} openAuthModal={() => {}} />
        )}

        {activeTab === "schedules" && (
          <SchedulesView t={t} openAuthModal={() => {}} />
        )}

        {activeTab === "recipes" && (
          <RecipesView
            t={t}
            onSelectRecipeForReapplication={(rec) => {
              // Handled within RecipesView modal
            }}
          />
        )}

        {activeTab === "history" && <HistoryView t={t} />}
      </main>

      <footer className="w-full border-t border-slate-200 dark:border-slate-800/80 py-6 text-center text-xs text-slate-400 dark:text-slate-500">
        <p>Anclora CleanSheet © 2026. Normalización determinista y reproducible.</p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <UIProvider>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/activate" element={<ActivateAccess />} />
            <Route
              path="/app"
              element={
                <ProtectedRoute>
                  <CleanSheetApp />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </UIProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
