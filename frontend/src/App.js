import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { debounce } from "lodash";
import { AuthProvider } from "./context/AuthContext";
import { translations } from "./i18n";

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
import AuthModal from "./components/AuthModal";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

const listUnique = (arr) => Array.from(new Set(arr));

function CleanSheetApp() {
  // Theme state: dark | light | system (persisted in localStorage, default dark)
  const [theme, setTheme] = useState(() => localStorage.getItem("cleansheet_theme") || "dark");
  // Language state: es | en (persisted in localStorage, default es)
  const [lang, setLang] = useState(() => localStorage.getItem("cleansheet_lang") || "es");

  const [activeTab, setActiveTab] = useState("clean"); // "clean" | "recipes" | "history"
  const [authModalOpen, setAuthModalOpen] = useState(false);

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

  // Persist Theme and handle System preference
  useEffect(() => {
    localStorage.setItem("cleansheet_theme", theme);
    const root = document.documentElement;
    root.classList.remove("dark", "light");

    if (theme === "system") {
      const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.classList.add(systemDark ? "dark" : "light");
    } else {
      root.classList.add(theme);
    }
  }, [theme]);

  // Persist Language
  useEffect(() => {
    localStorage.setItem("cleansheet_lang", lang);
  }, [lang]);

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
        const res = await axios.post(`${BACKEND_URL}/api/files/preview`, {
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
        lang={lang}
        setLang={setLang}
        theme={theme}
        setTheme={setTheme}
        t={t}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        openAuthModal={() => setAuthModalOpen(true)}
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
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:border-red-400 text-slate-600 dark:text-slate-400 hover:text-red-400 transition-colors self-start sm:self-auto"
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
                        await axios.post(
                          `${BACKEND_URL}/api/recipes/${currentFile.recipe_id}/aliases`,
                          { canonical_column: canonicalCol, alias: candCol },
                          { withCredentials: true }
                        );
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
                  openAuthModal={() => setAuthModalOpen(true)}
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
          <BatchProcessingView t={t} openAuthModal={() => setAuthModalOpen(true)} />
        )}

        {activeTab === "automations" && (
          <AutomationsView t={t} openAuthModal={() => setAuthModalOpen(true)} />
        )}

        {activeTab === "connectors" && (
          <ConnectorsView t={t} openAuthModal={() => setAuthModalOpen(true)} />
        )}

        {activeTab === "schedules" && (
          <SchedulesView t={t} openAuthModal={() => setAuthModalOpen(true)} />
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

      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        t={t}
      />

      <footer className="w-full border-t border-slate-200 dark:border-slate-800/80 py-6 text-center text-xs text-slate-400 dark:text-slate-500">
        <p>Anclora CleanSheet © 2026. Normalización determinista y reproducible.</p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <CleanSheetApp />
    </AuthProvider>
  );
}
