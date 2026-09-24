import React from "react";
import { Globe } from "lucide-react";
import { useUI } from "../context/UIContext";

export function LangToggle({ className = "" }) {
  const { lang, toggleLang } = useUI();

  return (
    <button
      type="button"
      data-testid="lang-toggle-button"
      onClick={toggleLang}
      title={lang === "es" ? "Switch to English" : "Cambiar a Español"}
      className={`flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider transition-all duration-200 border border-[#3B82F6]/40 hover:border-[#38BDF8] shadow-sm bg-[#0E1525] text-[#F5F7FA] hover:shadow-[#38BDF8]/20 focus:outline-none focus:ring-2 focus:ring-[#38BDF8] ${className}`}
    >
      <Globe className="w-3.5 h-3.5 text-[#38BDF8]" />
      <span>{lang.toUpperCase()}</span>
    </button>
  );
}

export default LangToggle;
