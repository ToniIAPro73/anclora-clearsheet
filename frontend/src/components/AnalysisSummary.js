import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, Info, Layers, Eye } from "lucide-react";

export default function AnalysisSummary({ analysis, t }) {
  if (!analysis) return null;

  const { transformations_summary, structure_fingerprint, columns, total_raw_rows } = analysis;

  const getConfidenceBadge = (confidence) => {
    if (confidence >= 0.85) {
      return (
        <span
          data-testid="confidence-badge-alta"
          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
        >
          {t.summary.confidence_alta} ({Math.round(confidence * 100)}%)
        </span>
      );
    } else if (confidence >= 0.65) {
      return (
        <span
          data-testid="confidence-badge-media"
          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30"
        >
          {t.summary.confidence_media} ({Math.round(confidence * 100)}%)
        </span>
      );
    } else {
      return (
        <span
          data-testid="confidence-badge-baja"
          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30"
        >
          {t.summary.confidence_baja} ({Math.round(confidence * 100)}%)
        </span>
      );
    }
  };

  return (
    <div
      data-testid="analysis-summary-card"
      className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm space-y-4"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800/80 pb-3">
        <div className="flex items-center space-x-2">
          <Layers className="w-5 h-5 text-[#38BDF8]" />
          <h4 className="text-base font-bold dark:text-white text-slate-900">{t.summary.title}</h4>
        </div>
        <div className="flex items-center space-x-2 text-xs text-slate-500 dark:text-slate-400">
          <span>{t.summary.fingerprint}</span>
          <code
            data-testid="structure-fingerprint-badge"
            className="px-2 py-0.5 rounded bg-slate-100 dark:bg-[#0E1525] border border-slate-300 dark:border-slate-700 font-mono text-[#38BDF8] font-semibold"
          >
            {structure_fingerprint}
          </code>
        </div>
      </div>

      {/* List of Detected Heuristic Transformations */}
      <div className="space-y-2.5">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          {t.summary.detected_problems} ({transformations_summary.length})
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {transformations_summary.map((item, idx) => {
            const isWarn = item.type.includes("warning") || item.type.includes("ambiguous");
            return (
              <div
                key={idx}
                data-testid={`transformation-item-${item.type}`}
                className={`p-3 rounded-xl border flex items-start justify-between gap-2 text-xs transition-colors ${
                  isWarn
                    ? "border-amber-500/30 bg-amber-500/5 text-amber-300"
                    : "border-slate-200 dark:border-slate-800 dark:bg-[#0E1525]/50 bg-slate-50/70"
                }`}
              >
                <div className="flex items-start space-x-2">
                  {isWarn ? (
                    <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 text-[#38BDF8] flex-shrink-0 mt-0.5" />
                  )}
                  <div>
                    <div className="font-semibold dark:text-slate-200 text-slate-800">
                      {item.label_es || item.label_en}
                    </div>
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      {item.detail_es || item.detail_en}
                    </div>
                  </div>
                </div>
                <div className="flex-shrink-0">{getConfidenceBadge(item.confidence)}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
