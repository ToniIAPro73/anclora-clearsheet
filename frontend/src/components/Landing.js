import React from "react";
import { Link, Navigate } from "react-router-dom";
import {
  Sparkles,
  ShieldCheck,
  Check,
  FileSpreadsheet,
  Cpu,
  Layers,
  ArrowRight,
  KeyRound
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useUI } from "../context/UIContext";
import { BrandMark } from "./BrandMark";
import LangToggle from "./LangToggle";
import ThemeToggle from "./ThemeToggle";

export default function Landing() {
  const { user, loading } = useAuth();
  const { lang } = useUI();
  const en = lang === "en";

  // Redirect authenticated user to protected workspace
  if (!loading && user) {
    return <Navigate to="/app" replace />;
  }

  const copy = en
    ? {
        eyebrow: "ANCLORA / DETERMINISTIC DATA NORMALIZATION",
        title: "From messy spreadsheets to data you can trust.",
        lead: "CleanSheet turns broken ERP, CRM, and banking exports into pristine, structured data ready for production. Zero hallucinations, reproducible YAML recipes, and automated batch processing.",
        signIn: "Sign in",
        howItWorks: "How it works",
        activate: "Have an invitation? Activate access",
        proof: "Exclusive invitation access · Deterministic normalization",
        valueEyebrow: "THE LAST MILE OF SPREADSHEETS",
        problem: "Stop wasting hours on spreadsheet archaeology.",
        problemLead: "Misaligned multi-row headers, mixed date formats, European decimal separators, and trailing blank rows. CleanSheet applies deterministic heuristics to normalize datasets instantly.",
        benefits: [
          "Automatic detection of title banners, headers, and CSV dialects",
          "Deterministic normalization of dates, amounts, and text aliases",
          "Export reproducible YAML recipes and standalone Python scripts",
          "Automated batch pipelines and scheduled cloud storage sync"
        ],
        flowEyebrow: "A DETERMINISTIC, REPRODUCIBLE FLOW",
        flowTitle: "From raw exports to dependable tabular data.",
        flow: [
          {
            title: "Upload & Heuristics",
            desc: "Drop messy Excel or CSV files. Instant heuristic detection of structure and format drift.",
            icon: FileSpreadsheet
          },
          {
            title: "Review & Compare",
            desc: "Inspect live before/after diffs with cell-level confidence and interactive rule tuning.",
            icon: Cpu
          },
          {
            title: "Export & Automate",
            desc: "Download clean data, export YAML recipes, or schedule autonomous cloud pipelines.",
            icon: Layers
          }
        ],
        closingEyebrow: "RELIABILITY AT SCALE",
        closing: "Make your enterprise tabular data accountable.",
        footer: "Deterministic and reproducible data normalization",
        terms: "Terms",
        privacy: "Privacy"
      }
    : {
        eyebrow: "ANCLORA / NORMALIZACIÓN DETERMINISTA DE DATOS",
        title: "De hojas caóticas a datos en los que puedes confiar.",
        lead: "CleanSheet transforma exportaciones rotas de ERPs, CRMs y extractos bancarios en tablas limpias y listas para producción. Cero alucinaciones, recetas YAML reproducibles y procesamiento por lotes.",
        signIn: "Iniciar sesión",
        howItWorks: "Ver cómo funciona",
        activate: "¿Tienes invitación? Activar acceso",
        proof: "Acceso exclusivo por invitación · Normalización determinista",
        valueEyebrow: "EL ÚLTIMO TRAMO DE LAS HOJAS DE CÁLCULO",
        problem: "Deja de perder horas en arqueología de hojas de cálculo.",
        problemLead: "Cabeceras desalineadas, fechas mezcladas, decimales europeos con puntos de miles y filas vacías. CleanSheet aplica heurísticas deterministas para resolver el desorden al instante.",
        benefits: [
          "Detección automática de banners, cabeceras y dialectos CSV",
          "Normalización determinista de fechas, importes y aliases",
          "Generación de recetas reproducibles en YAML y scripts Python autónomos",
          "Pipelines por lotes y sincronización programada con nubes y ERPs"
        ],
        flowEyebrow: "UN FLUJO DETERMINISTA Y REPRODUCIBLE",
        flowTitle: "De la exportación rota al dato fiable.",
        flow: [
          {
            title: "Carga y Heurística",
            desc: "Sube archivos Excel o CSV complejos. Detección instantánea de estructuras y desvíos.",
            icon: FileSpreadsheet
          },
          {
            title: "Revisa y Compara",
            desc: "Inspecciona la comparativa antes/después y afina reglas de transformación en tiempo real.",
            icon: Cpu
          },
          {
            title: "Exporta y Automatiza",
            desc: "Descarga tablas limpias, exporta recetas YAML o programa flujos automáticos en la nube.",
            icon: Layers
          }
        ],
        closingEyebrow: "FIABILIDAD A ESCALA",
        closing: "Haz que cada tabla sea trazable y estructurada.",
        footer: "Normalización determinista y reproducible de datos",
        terms: "Términos",
        privacy: "Privacidad"
      };

  return (
    <main className="landing-shell">
      {/* Top Navigation */}
      <nav className="landing-nav">
        <Link to="/" className="landing-brand">
          <BrandMark className="h-9 w-9 rounded-full shadow-sm shadow-[#38BDF8]/20" />
          <span>
            Anclora <b>CleanSheet</b>
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <a href="#how" className="landing-nav-link hidden sm:inline">
            {copy.howItWorks}
          </a>
          <LangToggle />
          <ThemeToggle />
          <Link to="/login" className="landing-nav-cta">
            {copy.signIn}
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-copy fade-up">
          <p className="landing-eyebrow">
            <Sparkles size={14} /> {copy.eyebrow}
          </p>
          <h1>{copy.title}</h1>
          <p className="landing-lead">{copy.lead}</p>
          <div className="landing-actions flex-wrap">
            <Link to="/login" className="landing-primary">
              <span>{copy.signIn}</span>
              <ArrowRight size={15} />
            </Link>
            <a href="#how" className="landing-text-link">
              {copy.howItWorks}
            </a>
          </div>
          <div className="mt-4">
            <Link
              to="/activate"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#38BDF8] hover:underline"
            >
              <KeyRound size={13} />
              <span>{copy.activate}</span>
            </Link>
          </div>
          <div className="landing-proof">
            <ShieldCheck size={17} />
            <span>{copy.proof}</span>
          </div>
        </div>

        {/* Hero Visual Card: Interactive CleanSheet Normalization Preview */}
        <div className="landing-hero-visual fade-up" style={{ animationDelay: "100ms" }}>
          <div className="landing-orbit landing-orbit-one" />
          <div className="landing-orbit landing-orbit-two" />
          <div className="landing-product-card">
            <div className="landing-card-top">
              <span className="landing-live-dot" />
              <span>{en ? "DETERMINISTIC NORMALIZER" : "NORMALIZADOR DETERMINISTA"}</span>
              <span className="ml-auto text-xs text-slate-400 font-mono">100% AUDITED</span>
            </div>

            {/* Before / After Mini Visual Comparison */}
            <div className="landing-doc-preview mt-3">
              <div className="flex justify-between items-center text-[10px] uppercase font-bold text-slate-500 mb-2 border-b border-slate-200 dark:border-slate-700/60 pb-1.5">
                <span className="text-red-500 dark:text-red-400">{en ? "RAW ERP EXPORT" : "ORIGINAL ERP"}</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{en ? "CLEANSHEET RESULT" : "NORMALIZADO"}</span>
              </div>
              <div className="space-y-1.5 font-mono text-[11px]">
                <div className="flex justify-between items-center bg-slate-100 dark:bg-slate-800/80 p-1.5 rounded">
                  <span className="line-through text-slate-400 dark:text-slate-500 text-[10px]">01/05/2026 | 1.250,50 €</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">2026-05-01 | 1250.50</span>
                </div>
                <div className="flex justify-between items-center bg-slate-100 dark:bg-slate-800/80 p-1.5 rounded">
                  <span className="line-through text-slate-400 dark:text-slate-500 text-[10px]">15.05.2026 | 3.400,00 €</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">2026-05-15 | 3400.00</span>
                </div>
                <div className="flex justify-between items-center bg-slate-100 dark:bg-slate-800/80 p-1.5 rounded">
                  <span className="line-through text-slate-400 dark:text-slate-500 text-[10px]">2026/05/18 | 850,75 €</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">2026-05-18 | 850.75</span>
                </div>
              </div>
            </div>

            <div className="landing-confidence mt-3">
              <span>
                <i className="confidence-green" /> {en ? "ISO-8601 Dates" : "Fechas ISO-8601"}
              </span>
              <span>
                <i className="confidence-green" /> {en ? "Normalized Decimals" : "Decimales Estándar"}
              </span>
              <span>
                <i className="confidence-green" /> {en ? "Deterministic Recipe" : "Receta YAML"}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Value / Problem Section */}
      <section className="landing-section landing-value">
        <p className="landing-eyebrow">{copy.valueEyebrow}</p>
        <h2>{copy.problem}</h2>
        <p className="landing-section-lead">{copy.problemLead}</p>
        <div className="landing-benefits">
          {copy.benefits.map((item) => (
            <div key={item} className="landing-benefit">
              <span>
                <Check size={15} />
              </span>
              <p>{item}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Workflow Section */}
      <section id="how" className="landing-section landing-flow">
        <div>
          <p className="landing-eyebrow">{copy.flowEyebrow}</p>
          <h2>{copy.flowTitle}</h2>
        </div>
        <div className="landing-flow-grid">
          {copy.flow.map((item, i) => {
            const Icon = item.icon;
            return (
              <div className="landing-flow-step" key={item.title}>
                <span>0{i + 1}</span>
                <div>
                  <Icon />
                  <h3>{item.title}</h3>
                  <p>{item.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="landing-closing">
        <p className="landing-eyebrow">{copy.closingEyebrow}</p>
        <h2>{copy.closing}</h2>
        <div className="flex flex-col items-center gap-3">
          <Link to="/login" className="landing-primary">
            <span>{copy.signIn}</span>
            <ArrowRight size={15} />
          </Link>
          <Link to="/activate" className="text-xs text-[#38BDF8] hover:underline font-semibold mt-2">
            {copy.activate}
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <span>© 2026 Anclora CleanSheet</span>
        <span>{copy.footer}</span>
        <span>
          <span className="text-slate-400">v1.0 · Private Whitelist</span>
        </span>
      </footer>
    </main>
  );
}
