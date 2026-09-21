import React, { useState } from "react";
import { Lock, Mail, User, AlertCircle, Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function AuthModal({ isOpen, onClose, t }) {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        await register(email, password, name);
      } else {
        await login(email, password);
      }
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || t.auth_modal.error_generic);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      data-testid="auth-modal-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-700 dark:bg-[#0B1220] bg-white p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
          <h3 className="text-base font-bold dark:text-white text-slate-900">
            {isRegister ? t.auth_modal.title_register : t.auth_modal.title_login}
          </h3>
          <button
            data-testid="auth-modal-close"
            onClick={onClose}
            className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          {isRegister && (
            <div>
              <label className="text-slate-400 font-medium block mb-1">{t.auth_modal.name}</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  data-testid="input-auth-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Juan Pérez"
                  className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white focus:outline-none focus:border-[#38BDF8]"
                />
              </div>
            </div>
          )}

          <div>
            <label className="text-slate-400 font-medium block mb-1">{t.auth_modal.email}</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="email"
                required
                data-testid="input-auth-email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@empresa.com"
                className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white focus:outline-none focus:border-[#38BDF8]"
              />
            </div>
          </div>

          <div>
            <label className="text-slate-400 font-medium block mb-1">{t.auth_modal.password}</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="password"
                required
                data-testid="input-auth-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] bg-white text-slate-900 dark:text-white focus:outline-none focus:border-[#38BDF8]"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            data-testid="auth-submit-btn"
            className="w-full py-2.5 rounded-xl font-semibold bg-[#3B82F6] hover:bg-[#2563EB] text-white flex items-center justify-center space-x-2 transition-all shadow-md shadow-[#3B82F6]/20"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{isRegister ? t.auth_modal.btn_register : t.auth_modal.btn_login}</span>
          </button>
        </form>

        <div className="pt-2 text-center">
          <button
            type="button"
            data-testid="auth-toggle-mode-btn"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
            className="text-xs text-[#38BDF8] hover:underline"
          >
            {isRegister ? t.auth_modal.toggle_to_login : t.auth_modal.toggle_to_register}
          </button>
        </div>
      </div>
    </div>
  );
}
