import React, { useState } from "react";
import { Globe, Sun, Moon, Laptop, Sparkles, LogIn, LogOut, User as UserIcon, Menu, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Header({
  lang,
  setLang,
  theme,
  setTheme,
  t,
  activeTab,
  setActiveTab,
  openAuthModal
}) {
  const { user, logout } = useAuth();
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleLanguage = () => {
    setLang(lang === "es" ? "en" : "es");
  };

  return (
    <header
      data-testid="app-sticky-header"
      className="sticky top-0 z-50 w-full backdrop-blur-md transition-colors duration-200 border-b border-[#3B82F6]/30 dark:bg-[#0E1525]/90 bg-white/95"
    >
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand & Placeholder Logo */}
        <div className="flex items-center space-x-2 sm:space-x-3 cursor-pointer shrink-0" onClick={() => setActiveTab("clean")}>
          <div
            data-testid="brand-logo-placeholder"
            className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-gradient-to-tr from-[#3B82F6] to-[#38BDF8] flex items-center justify-center shadow-sm shadow-[#38BDF8]/20"
          >
            <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
          </div>
          <div>
            <div className="text-base sm:text-lg font-bold tracking-tight dark:text-white text-slate-900 flex items-center gap-1">
              <span>Anclora</span>
              <span className="text-[#38BDF8] font-extrabold">CleanSheet</span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center space-x-1">
          <button
            data-testid="nav-clean-tab"
            onClick={() => setActiveTab("clean")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "clean"
                ? "bg-[#3B82F6]/15 text-[#38BDF8] dark:text-[#38BDF8] border border-[#3B82F6]/40"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.nav.clean}
          </button>
          <button
            data-testid="nav-stream-tab"
            onClick={() => setActiveTab("stream")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "stream"
                ? "bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/40"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.nav.stream}
          </button>
          <button
            data-testid="nav-batch-tab"
            onClick={() => setActiveTab("batch")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "batch"
                ? "bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/40"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.nav.batch}
          </button>
          <button
            data-testid="nav-automations-tab"
            onClick={() => setActiveTab("automations")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "automations"
                ? "bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/40"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {t.nav.automations}
          </button>
          {user && (
            <>
              <button
                data-testid="nav-connectors-tab"
                onClick={() => setActiveTab("connectors")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeTab === "connectors"
                    ? "bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/40"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                {t.nav.connectors}
              </button>
              <button
                data-testid="nav-schedules-tab"
                onClick={() => setActiveTab("schedules")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeTab === "schedules"
                    ? "bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/40"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                {t.nav.schedules}
              </button>
              <button
                data-testid="nav-recipes-tab"
                onClick={() => setActiveTab("recipes")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeTab === "recipes"
                    ? "bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/40"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                {t.nav.recipes}
              </button>
              <button
                data-testid="nav-history-tab"
                onClick={() => setActiveTab("history")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeTab === "history"
                    ? "bg-[#3B82F6]/15 text-[#38BDF8] border border-[#3B82F6]/40"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                {t.nav.history}
              </button>
            </>
          )}
        </nav>

        {/* Right Controls: Language Selector Pill & Theme Circle */}
        <div className="flex items-center space-x-2 shrink-0">
          {/* Language Selector Pill */}
          <button
            data-testid="lang-toggle-pill"
            onClick={toggleLanguage}
            title={lang === "es" ? "Switch to English" : "Cambiar a Español"}
            className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider transition-all duration-200 border border-[#3B82F6]/40 hover:border-[#38BDF8] shadow-sm bg-[#0E1525] text-[#F5F7FA] hover:shadow-[#38BDF8]/20 focus:outline-none focus:ring-2 focus:ring-[#38BDF8]"
          >
            <Globe className="w-3.5 h-3.5 text-[#38BDF8]" />
            <span>{lang.toUpperCase()}</span>
          </button>

          {/* Theme Selector Circle with Dropdown Menu */}
          <div className="relative">
            <button
              data-testid="theme-toggle-button"
              onClick={() => setThemeMenuOpen(!themeMenuOpen)}
              title="Cambiar tema / Switch theme"
              className="w-8 h-8 rounded-full flex items-center justify-center transition-all duration-200 border border-[#3B82F6]/40 hover:border-[#38BDF8] bg-[#0E1525] text-[#F5F7FA] hover:shadow-[#38BDF8]/20 focus:outline-none focus:ring-2 focus:ring-[#38BDF8]"
            >
              {theme === "dark" && <Moon className="w-4 h-4 text-[#38BDF8]" />}
              {theme === "light" && <Sun className="w-4 h-4 text-amber-400" />}
              {theme === "system" && <Laptop className="w-4 h-4 text-slate-300" />}
            </button>

            {themeMenuOpen && (
              <div
                data-testid="theme-dropdown-menu"
                className="absolute right-0 mt-2 w-36 rounded-lg shadow-xl py-1 z-50 border border-slate-700 dark:bg-[#0B1220] bg-white text-xs font-medium"
              >
                <button
                  data-testid="theme-option-dark"
                  onClick={() => {
                    setTheme("dark");
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
                    theme === "dark" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
                  }`}
                >
                  <Moon className="w-3.5 h-3.5 text-[#38BDF8]" />
                  <span>Oscuro</span>
                </button>
                <button
                  data-testid="theme-option-light"
                  onClick={() => {
                    setTheme("light");
                    setThemeMenuOpen(false);
                  }}
                  className={`w-full px-3 py-2 flex items-center space-x-2 text-left hover:bg-[#3B82F6]/10 ${
                    theme === "light" ? "text-[#38BDF8] font-bold" : "text-slate-700 dark:text-slate-300"
                  }`}
                >
                  <Sun className="w-3.5 h-3.5 text-amber-500" />
                  <span>Claro</span>
                </button>
                <button
                  data-testid="theme-option-system"
                  onClick={() => {
                    setTheme("system");
                    setThemeMenuOpen(false);
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

          {/* User Auth Action Button */}
          {user ? (
            <div className="flex items-center space-x-2">
              <span className="hidden sm:inline-block text-xs font-medium text-slate-500 dark:text-slate-400">
                {user.email}
              </span>
              <button
                data-testid="auth-logout-button"
                onClick={logout}
                title={t.nav.logout}
                className="p-1.5 rounded-md text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              data-testid="auth-login-button"
              onClick={openAuthModal}
              className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-[#3B82F6]/15 hover:bg-[#3B82F6]/25 text-[#38BDF8] border border-[#3B82F6]/40 transition-all flex items-center space-x-1 shadow-sm"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t.nav.sign_in}</span>
            </button>
          )}

          {/* Mobile Hamburger Button */}
          <button
            data-testid="btn-mobile-menu-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-1.5 rounded-md text-slate-400 hover:text-white"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-700 dark:bg-[#0B1220] bg-white px-4 py-3 space-y-2">
          <button
            onClick={() => { setActiveTab("clean"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "clean" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.clean}
          </button>
          <button
            onClick={() => { setActiveTab("stream"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "stream" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.stream}
          </button>
          <button
            onClick={() => { setActiveTab("batch"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "batch" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.batch}
          </button>
          <button
            onClick={() => { setActiveTab("automations"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "automations" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.automations}
          </button>
          <button
            onClick={() => { setActiveTab("connectors"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "connectors" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.connectors}
          </button>
          <button
            onClick={() => { setActiveTab("schedules"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "schedules" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.schedules}
          </button>
          <button
            onClick={() => { setActiveTab("recipes"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "recipes" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.recipes}
          </button>
          <button
            onClick={() => { setActiveTab("history"); setMobileMenuOpen(false); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-semibold ${activeTab === "history" ? "bg-[#3B82F6]/15 text-[#38BDF8]" : "text-slate-400"}`}
          >
            {t.nav.history}
          </button>
        </div>
      )}
    </header>
  );
}
