import React, { createContext, useContext, useState, useEffect } from "react";

const UIContext = createContext(null);

export const UIProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => localStorage.getItem("cleansheet_theme") || "dark");
  const [lang, setLang] = useState(() => localStorage.getItem("cleansheet_lang") || "es");

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

  useEffect(() => {
    localStorage.setItem("cleansheet_lang", lang);
  }, [lang]);

  const toggleLang = () => setLang((prev) => (prev === "es" ? "en" : "es"));

  return (
    <UIContext.Provider value={{ theme, setTheme, lang, setLang, toggleLang }}>
      {children}
    </UIContext.Provider>
  );
};

export const useUI = () => useContext(UIContext);
