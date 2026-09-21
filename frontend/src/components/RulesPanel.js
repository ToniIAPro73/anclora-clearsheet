import React, { useState } from "react";
import { Sliders, RefreshCw, AlertCircle } from "lucide-react";

export default function RulesPanel({
  rules,
  onChangeRule,
  onRecalculate,
  isRecalculating,
  analysis,
  t
}) {
  if (!rules) return null;

  return (
    <div
      data-testid="rules-panel-container"
      className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white shadow-sm space-y-5"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800/80 pb-3">
        <div className="flex items-center space-x-2">
          <Sliders className="w-5 h-5 text-[#38BDF8]" />
          <div>
            <h4 className="text-base font-bold dark:text-white text-slate-900 flex items-center gap-2">
              <span>{t.rules.title}</span>
              <span
                data-testid="preset-hybrid-badge"
                className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/30"
              >
                {t.rules.preset_badge}
              </span>
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{t.rules.subtitle}</p>
          </div>
        </div>

        {isRecalculating && (
          <div className="flex items-center space-x-1.5 text-xs text-[#38BDF8] animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            <span>{t.rules.recalculating}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 text-xs">
        {/* Group 1: Locale & Decimals */}
        <div className="space-y-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0E1525]/40 bg-slate-50/50">
          <p className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px] text-[#38BDF8]">
            {t.rules.group_locale}
          </p>

          <div className="space-y-1">
            <label className="text-slate-500 dark:text-slate-400 font-medium">{t.rules.decimal_separator}</label>
            <select
              data-testid="rule-select-decimal-separator"
              value={rules.decimal_separator || ","}
              onChange={(e) => onChangeRule("decimal_separator", e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0B1220] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
            >
              <option value=",">Coma ( , ) - Estándar europeo / es-ES</option>
              <option value=".">Punto ( . ) - Estándar US / en-US</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-slate-500 dark:text-slate-400 font-medium">{t.rules.thousands_separator}</label>
            <select
              data-testid="rule-select-thousands-separator"
              value={rules.thousands_separator || "."}
              onChange={(e) => onChangeRule("thousands_separator", e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0B1220] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
            >
              <option value=".">Punto ( . ) - ej. 1.250,50</option>
              <option value=",">Coma ( , ) - ej. 1,250.50</option>
              <option value=" ">Espacio ( )</option>
              <option value="">Ninguno</option>
            </select>
          </div>
        </div>

        {/* Group 2: Dates */}
        <div className="space-y-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0E1525]/40 bg-slate-50/50">
          <p className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px] text-[#38BDF8]">
            {t.rules.group_dates}
          </p>

          <div className="space-y-1">
            <label className="text-slate-500 dark:text-slate-400 font-medium">{t.rules.date_output}</label>
            <select
              data-testid="rule-select-date-output"
              value={rules.date_output_format || "YYYY-MM-DD"}
              onChange={(e) => onChangeRule("date_output_format", e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0B1220] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
            >
              <option value="YYYY-MM-DD">ISO YYYY-MM-DD (Recomendado)</option>
              <option value="DD/MM/YYYY">DD/MM/YYYY</option>
              <option value="MM/DD/YYYY">MM/DD/YYYY</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-slate-500 dark:text-slate-400 font-medium">{t.rules.date_preference}</label>
            <select
              data-testid="rule-select-date-preference"
              value={rules.date_input_preference || "auto"}
              onChange={(e) => onChangeRule("date_input_preference", e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0B1220] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
            >
              <option value="auto">{t.rules.pref_auto}</option>
              <option value="DMY">{t.rules.pref_dmy}</option>
              <option value="MDY">{t.rules.pref_mdy}</option>
            </select>
          </div>
        </div>

        {/* Group 3: Structure & Headers */}
        <div className="space-y-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0E1525]/40 bg-slate-50/50">
          <p className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[11px] text-[#38BDF8]">
            {t.rules.group_structure}
          </p>

          <div className="space-y-1">
            <label className="text-slate-500 dark:text-slate-400 font-medium">{t.rules.skip_title_rows}</label>
            <input
              type="number"
              min="0"
              max="25"
              data-testid="rule-input-skip-rows"
              value={rules.remove_top_rows ?? 0}
              onChange={(e) => onChangeRule("remove_top_rows", parseInt(e.target.value) || 0)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0B1220] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-slate-600 dark:text-slate-300">{t.rules.remove_empty_rows}</span>
            <input
              type="checkbox"
              data-testid="rule-checkbox-empty-rows"
              checked={rules.remove_empty_rows ?? true}
              onChange={(e) => onChangeRule("remove_empty_rows", e.target.checked)}
              className="w-4 h-4 rounded text-[#38BDF8] focus:ring-[#38BDF8]"
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-slate-600 dark:text-slate-300">{t.rules.remove_empty_cols}</span>
            <input
              type="checkbox"
              data-testid="rule-checkbox-empty-cols"
              checked={rules.remove_empty_columns ?? true}
              onChange={(e) => onChangeRule("remove_empty_columns", e.target.checked)}
              className="w-4 h-4 rounded text-[#38BDF8] focus:ring-[#38BDF8]"
            />
          </div>
        </div>
      </div>

      {/* Header Naming Policy (Conservative by default) */}
      <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0E1525]/30 bg-slate-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div>
          <span className="font-bold text-slate-700 dark:text-slate-300">{t.rules.header_casing}:</span>
          <span className="text-slate-500 dark:text-slate-400 ml-2">
            Por criterio conservador no destructivo, los nombres se mantienen tal cual salvo activación explícita.
          </span>
        </div>
        <select
          data-testid="rule-select-header-casing"
          value={rules.normalize_headers_case || "preserve"}
          onChange={(e) => onChangeRule("normalize_headers_case", e.target.value)}
          className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0B1220] bg-white text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#38BDF8]"
        >
          <option value="preserve">{t.rules.casing_preserve}</option>
          <option value="snake_case">{t.rules.casing_snake}</option>
        </select>
      </div>
    </div>
  );
}
