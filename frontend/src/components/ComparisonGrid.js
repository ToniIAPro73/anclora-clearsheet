import React, { useState } from "react";
import { Columns, LayoutList, Info, HelpCircle } from "lucide-react";

export default function ComparisonGrid({ original, normalized, t }) {
  const [viewMode, setViewMode] = useState("split"); // "split" | "tabs"
  const [activeMobileTab, setActiveMobileTab] = useState("after"); // "before" | "after"
  const [selectedCell, setSelectedCell] = useState(null);

  if (!normalized) return null;

  const originalRows = original?.rows || [];
  const normalizedRows = normalized?.rows || [];
  const normalizedHeaders = normalized?.headers || [];
  const changes = normalized?.changes_sample || [];

  // Map changes for quick cell lookup: "row_col" -> change
  const changesMap = {};
  changes.forEach((c) => {
    changesMap[`${c.row}_${c.col}`] = c;
  });

  return (
    <div
      data-testid="comparison-grid-section"
      className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm space-y-4"
    >
      {/* View Switcher Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800/80 pb-3">
        <div>
          <h4 className="text-base font-bold dark:text-white text-slate-900 flex items-center gap-2">
            <Columns className="w-5 h-5 text-[#38BDF8]" />
            <span>{t.comparison.title}</span>
            <span
              data-testid="changes-count-badge"
              className="text-xs font-semibold px-2 py-0.5 rounded bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/30"
            >
              {normalized.changes_count || changes.length} {t.comparison.changes_count}
            </span>
          </h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{t.comparison.sample_notice}</p>
        </div>

        {/* Desktop Split Toggle vs Mobile Tabs */}
        <div className="flex items-center space-x-1 p-1 rounded-lg bg-slate-100 dark:bg-[#0E1525] border border-slate-200 dark:border-slate-800 text-xs">
          <button
            data-testid="view-toggle-split"
            onClick={() => setViewMode("split")}
            className={`px-2.5 py-1 rounded-md font-medium transition-all ${
              viewMode === "split"
                ? "bg-white dark:bg-[#3B82F6] text-slate-900 dark:text-white shadow-sm"
                : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.comparison.view_mode_split}
          </button>
          <button
            data-testid="view-toggle-tabs"
            onClick={() => setViewMode("tabs")}
            className={`px-2.5 py-1 rounded-md font-medium transition-all ${
              viewMode === "tabs"
                ? "bg-white dark:bg-[#3B82F6] text-slate-900 dark:text-white shadow-sm"
                : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.comparison.view_mode_tabs}
          </button>
        </div>
      </div>

      {/* Mobile Tab Selectors if in Tabs view */}
      {viewMode === "tabs" && (
        <div className="flex border-b border-slate-200 dark:border-slate-800 text-xs font-semibold">
          <button
            data-testid="tab-button-before"
            onClick={() => setActiveMobileTab("before")}
            className={`px-4 py-2 border-b-2 transition-all ${
              activeMobileTab === "before"
                ? "border-[#38BDF8] text-[#38BDF8]"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.comparison.tab_before}
          </button>
          <button
            data-testid="tab-button-after"
            onClick={() => setActiveMobileTab("after")}
            className={`px-4 py-2 border-b-2 transition-all ${
              activeMobileTab === "after"
                ? "border-[#38BDF8] text-[#38BDF8]"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.comparison.tab_after}
          </button>
        </div>
      )}

      {/* Grid Display Area */}
      <div
        className={`grid gap-4 ${
          viewMode === "split" ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1"
        }`}
      >
        {/* Panel 1: Original Raw Data */}
        {(viewMode === "split" || activeMobileTab === "before") && (
          <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden flex flex-col bg-slate-50/50 dark:bg-[#0E1525]/30">
            <div className="px-3.5 py-2 border-b border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-[#0E1525] text-xs font-bold text-slate-600 dark:text-slate-300 flex justify-between items-center">
              <span>{t.comparison.tab_before}</span>
              <span className="text-[11px] font-normal text-slate-400">
                {originalRows.length} filas en muestra
              </span>
            </div>
            <div
              data-testid="table-original-container"
              className="overflow-auto max-h-[380px] text-xs font-mono"
            >
              <table className="w-full border-collapse">
                <tbody>
                  {originalRows.slice(0, 50).map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className="border-b border-slate-200/60 dark:border-slate-800/60 hover:bg-slate-200/40 dark:hover:bg-slate-800/40"
                    >
                      <td className="px-2.5 py-1.5 text-[10px] text-slate-400 bg-slate-100/40 dark:bg-[#0B1220] select-none w-8 text-center border-r border-slate-200 dark:border-slate-800">
                        {rIdx + 1}
                      </td>
                      {row.map((cell, cIdx) => (
                        <td
                          key={cIdx}
                          className="px-2.5 py-1.5 whitespace-nowrap text-slate-600 dark:text-slate-400 max-w-[200px] truncate"
                        >
                          {cell !== null && cell !== undefined ? String(cell) : ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Panel 2: Normalized Clean Data with Interactive Highlighted Changes */}
        {(viewMode === "split" || activeMobileTab === "after") && (
          <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden flex flex-col bg-slate-50/50 dark:bg-[#0E1525]/30">
            <div className="px-3.5 py-2 border-b border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-[#0E1525] text-xs font-bold text-[#38BDF8] flex justify-between items-center">
              <span>{t.comparison.tab_after}</span>
              <span className="text-[11px] font-normal text-slate-400">
                {normalizedRows.length} filas normalizadas
              </span>
            </div>
            <div
              data-testid="table-normalized-container"
              className="overflow-auto max-h-[380px] text-xs font-mono"
            >
              <table className="w-full border-collapse">
                <thead className="sticky top-0 bg-white dark:bg-[#0B1220] border-b border-slate-300 dark:border-slate-700 shadow-sm z-10">
                  <tr>
                    <th className="px-2.5 py-2 text-[10px] text-slate-400 bg-slate-100 dark:bg-[#0E1525] w-8 text-center border-r border-slate-200 dark:border-slate-800">
                      #
                    </th>
                    {normalizedHeaders.map((head, hIdx) => (
                      <th
                        key={hIdx}
                        data-testid={`column-header-${hIdx}`}
                        className="px-3 py-2 text-left text-xs font-bold text-slate-800 dark:text-slate-200 whitespace-nowrap border-r border-slate-200 dark:border-slate-800"
                      >
                        {head}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {normalizedRows.slice(0, 50).map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className="border-b border-slate-200/60 dark:border-slate-800/60 hover:bg-slate-200/40 dark:hover:bg-slate-800/40"
                    >
                      <td className="px-2.5 py-1.5 text-[10px] text-slate-400 bg-slate-100/40 dark:bg-[#0B1220] select-none w-8 text-center border-r border-slate-200 dark:border-slate-800">
                        {rIdx + 1}
                      </td>
                      {row.map((cell, cIdx) => {
                        const changeInfo = changesMap[`${rIdx}_${cIdx}`];
                        const isModified = !!changeInfo;

                        return (
                          <td
                            key={cIdx}
                            onClick={() => {
                              if (changeInfo) {
                                setSelectedCell(changeInfo);
                              } else {
                                setSelectedCell({
                                  row: rIdx,
                                  col: cIdx,
                                  column_name: normalizedHeaders[cIdx],
                                  original: String(cell ?? ""),
                                  normalized: String(cell ?? ""),
                                  rule: "sin_modificacion",
                                  reason: "Valor conservado idéntico al original."
                                });
                              }
                            }}
                            title={isModified ? "Clic para ver detalle de la transformación" : "Valor sin cambios"}
                            className={`px-3 py-1.5 whitespace-nowrap max-w-[200px] truncate border-r border-slate-100 dark:border-slate-800/60 cursor-pointer transition-colors ${
                              isModified
                                ? "bg-[#38BDF8]/15 text-[#38BDF8] font-semibold border-l-2 border-l-[#38BDF8]"
                                : "text-slate-700 dark:text-slate-300 hover:bg-slate-100/50 dark:hover:bg-slate-800/20"
                            }`}
                          >
                            {cell !== null && cell !== undefined ? String(cell) : ""}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Selected Cell Audit Modal / Detail Box */}
      {selectedCell && (
        <div
          data-testid="cell-change-audit-box"
          className="p-3.5 rounded-xl border border-[#38BDF8]/40 bg-[#38BDF8]/10 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
        >
          <div className="space-y-1">
            <div className="font-bold text-[#38BDF8] flex items-center gap-1.5">
              <Info className="w-4 h-4" />
              <span>
                {t.comparison.cell_inspection_title}: Fila {selectedCell.row + 1}, Columna "
                {selectedCell.column_name}"
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 text-slate-700 dark:text-slate-300">
              <div>
                <span className="text-slate-400 text-[10px] block">
                  {t.comparison.cell_inspection_original}
                </span>
                <span className="font-mono bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded">
                  {selectedCell.original || "(vacío)"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] block">
                  {t.comparison.cell_inspection_normalized}
                </span>
                <span className="font-mono bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded">
                  {selectedCell.normalized}
                </span>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] block">
                  {t.comparison.cell_inspection_rule}
                </span>
                <span className="font-semibold text-[#38BDF8]">{selectedCell.rule}</span>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] block">
                  {t.comparison.cell_inspection_reason}
                </span>
                <span>{selectedCell.reason}</span>
              </div>
            </div>
          </div>

          <button
            onClick={() => setSelectedCell(null)}
            className="px-2.5 py-1 text-xs rounded border border-slate-300 dark:border-slate-700 hover:bg-white dark:hover:bg-[#0E1525]"
          >
            {t.export.close}
          </button>
        </div>
      )}
    </div>
  );
}
