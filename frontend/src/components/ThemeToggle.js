import React, { useState } from "react";
import { Sun, Moon, Laptop } from "lucide-react";
import { useUI } from "../context/UIContext";

export function ThemeToggle({ className = "" }) {
  const { theme, setTheme } = useUI();
  const [open, setOpen] = useState(false);

  return (
    <div className={`relative ${className}`}>
      <button
        type="button"
        data-testid="theme-toggle-button"
        onClick={() => setOpen(!open)}
        title="Cambiar tema / Switch theme"
        className="w-8 h-8 rounded-full flex items-center justify-center transition-all duration-200 border border-[#3B82F6]/40 hover:border-[#38BDF8] bg-[#0E1525] text-[#F5F7FA] hover:shadow-[#38BDF8]/20 focus:outline-none focus:ring-2 focus:ring-[#38BDF8]"
      >
        {theme === "dark" && <Moon className="w-4 h-4 text-[#38BDF8]" />}
        {theme === "light" && <Sun className="w-4 h-4 text-amber-400" />}
        {theme === "system" && <Laptop className="w-4 h-4 text-slate-300" />}
      </button>

      {open && (
        <div
          data-testid="theme-dropdown-menu"
          className="absolute right-0 mt-2 w-36 rounded-lg shadow-xl py-1 z-50 border border-slate-700 dark:bg-[#0B1220] bg-white text-xs font-medium"
        >
          <button
            type="button"
            data-testid="theme-option-dark"
            onClick={() => {
              setTheme("dark");
              setOpen(false);
            }}
            className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
              theme === "dark" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
            }`}
          >
            <Moon className="w-3.5 h-3.5 text-[#38BDF8]" />
            <span>Oscuro</span>
          </button>
          <button
            type="button"
            data-testid="theme-option-light"
            onClick={() => {
              setTheme("light");
              setOpen(false);
            }}
            className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
              theme === "light" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
            }`}
          >
            <Sun className="w-3.5 h-3.5 text-amber-500" />
            <span>Claro</span>
          </button>
          <button
            type="button"
            data-testid="theme-option-system"
            onClick={() => {
              setTheme("system");
              setOpen(false);
            }}
            className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
              theme === "system" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
            }`}
          >
            <Laptop className="w-3.5 h-3.5 text-slate-400" />
            <span>Sistema</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default ThemeToggle;
