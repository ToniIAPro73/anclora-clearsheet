import React, { useState } from "react";
import { Link, useNavigate, Navigate } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useUI } from "../context/UIContext";
import { BrandMark } from "./BrandMark";
import LangToggle from "./LangToggle";
import ThemeToggle from "./ThemeToggle";

export default function Login() {
  const { user, login, loading } = useAuth();
  const { lang } = useUI();
  const en = lang === "en";
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // If already authenticated, redirect to workspace
  if (!loading && user) {
    return <Navigate to="/app" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await login(email.trim().toLowerCase(), password);
      navigate("/app");
    } catch (err) {
      // Generic error message without revealing user existence or enumeration
      setError(
        en
          ? "Invalid email or password. Please verify your credentials."
          : "Credenciales incorrectas. Comprueba tu correo y contraseña."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      {/* Top Controls */}
      <div className="auth-top">
        <Link to="/" className="auth-back">
          <ArrowLeft size={15} />
          <span>{en ? "Back to site" : "Volver al sitio"}</span>
        </Link>
        <div className="flex items-center gap-2">
          <LangToggle />
          <ThemeToggle />
        </div>
      </div>

      <div className="auth-glow auth-glow-one" />
      <div className="auth-glow auth-glow-two" />

      {/* Login Card */}
      <section className="auth-card">
        <div className="auth-card-header">
          <BrandMark className="auth-logo rounded-full" />
          <div className="auth-divider" />
          <p className="tracking-tight text-base font-bold">
            Anclora <span className="text-[#38BDF8]">CleanSheet</span>
          </p>
          <span className="text-xs text-slate-400 mt-1 block">
            {en ? "Workspace Access" : "Acceso al Workspace"}
          </span>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {/* Email */}
          <label htmlFor="login-email">{en ? "Work Email" : "Correo electrónico"}</label>
          <input
            id="login-email"
            data-testid="login-email-input"
            type="email"
            autoComplete="email"
            required
            aria-required="true"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            disabled={submitting}
          />

          {/* Password */}
          <label htmlFor="login-password">{en ? "Password" : "Contraseña"}</label>
          <div className="auth-password">
            <input
              id="login-password"
              data-testid="login-password-input"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              aria-required="true"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
            />
            <button
              type="button"
              data-testid="login-password-toggle"
              aria-label={showPassword ? (en ? "Hide password" : "Ocultar contraseña") : (en ? "Show password" : "Mostrar contraseña")}
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div role="alert" data-testid="login-error" className="auth-error">
              {error}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            data-testid="login-submit-button"
            className="auth-submit cursor-pointer"
            disabled={submitting || !email || !password}
          >
            {submitting ? (en ? "Signing in..." : "Iniciando sesión...") : (en ? "Sign in" : "Iniciar sesión")}
          </button>

          {/* Whitelist / Invitation Link */}
          <div className="auth-invite mt-3 flex items-center justify-between">
            <span className="text-slate-400">
              {en ? "Access is by invitation only." : "Acceso exclusivo por invitación."}
            </span>
            <Link
              to="/activate"
              className="font-bold text-[#38BDF8] hover:underline"
            >
              <span>{en ? "Activate access" : "Activar acceso"}</span>
            </Link>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-700/50 flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck size={13} className="text-[#38BDF8]" />
            <span>{en ? "Secure Argon2 & JWT authentication" : "Autenticación segura con Argon2 y JWT"}</span>
          </div>
        </form>
      </section>
    </main>
  );
}
