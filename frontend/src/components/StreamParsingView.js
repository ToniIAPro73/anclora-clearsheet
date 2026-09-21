import React, { useState } from "react";
import { Zap, Download, Loader2, ArrowRight, CheckCircle2, FileText, Database } from "lucide-react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function StreamParsingView({ t }) {
  const [file, setFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [fileName, setFileName] = useState("");
  const [manualDelimiter, setManualDelimiter] = useState("");
  const [dialectInfo, setDialectInfo] = useState(null);
  const [detecting, setDetecting] = useState(false);

  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (!selected.name.toLowerCase().endsWith(".csv")) {
        alert("El modo streaming está especialmente optimizado para archivos CSV grandes (.csv).");
        return;
      }
      setFile(selected);
      setCompleted(false);
      setDownloadUrl(null);
      setDialectInfo(null);

      // Trigger automatic delimiter dialect detection
      setDetecting(true);
      try {
        const formData = new FormData();
        formData.append("file", selected);
        const res = await axios.post(`${BACKEND_URL}/api/files/detect-dialect`, formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
        setDialectInfo(res.data);
      } catch (err) {
        console.error("Dialect detection failed:", err);
      } finally {
        setDetecting(false);
      }
    }
  };

  const handleStartStream = async () => {
    if (!file) return;
    setProcessing(true);
    setCompleted(false);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("output_format", "csv");
      if (manualDelimiter) {
        formData.append("manual_delimiter", manualDelimiter);
      }

      const res = await axios.post(`${BACKEND_URL}/api/files/stream-process`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        responseType: "blob",
        withCredentials: true
      });

      const url = window.URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      setDownloadUrl(url);
      setFileName(`clean_${file.name}`);
      setCompleted(true);
    } catch (err) {
      alert("Error al procesar archivo en streaming.");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold dark:text-white text-slate-900 flex items-center gap-2">
          <Database className="w-5 h-5 text-[#38BDF8]" />
          <span>Stream Parsing Chunked CSV (Hasta 250 MB)</span>
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Procesamiento de archivos CSV masivos mediante lectura secuencial por bloques (chunks) con Polars sin agotar la memoria RAM.
        </p>
      </div>

      <div
        data-testid="stream-dropzone"
        className="p-8 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-800 dark:bg-[#0B1220] bg-white text-center space-y-4"
      >
        <div className="w-12 h-12 rounded-xl bg-[#3B82F6]/15 flex items-center justify-center mx-auto text-[#38BDF8]">
          <FileText className="w-6 h-6" />
        </div>
        <div>
          <h4 className="text-sm font-bold dark:text-white text-slate-900">
            Selecciona un archivo CSV pesado
          </h4>
          <p className="text-xs text-slate-400 mt-1">
            Soporta archivos de hasta 250 MB y más de 1.000.000 de filas procesados por chunks.
          </p>
        </div>

        <input
          type="file"
          accept=".csv"
          data-testid="stream-file-input"
          onChange={handleFileChange}
          className="text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-[#3B82F6] file:text-white hover:file:bg-[#2563EB] cursor-pointer"
        />

        {file && (
          <div className="text-xs font-semibold text-[#38BDF8] pt-2">
            Archivo preparado: {file.name} ({(file.size / (1024 * 1024)).toFixed(2)} MB)
          </div>
        )}
      </div>

      {/* Dialect Detection Results & Manual Override Box */}
      {file && (
        <div
          data-testid="dialect-detection-box"
          className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white space-y-3 text-xs"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
            <span className="font-bold dark:text-white text-slate-800">
              Detección Automática de Delimitador y Formato
            </span>
            {detecting && (
              <span className="text-[#38BDF8] flex items-center gap-1 text-[11px] animate-pulse">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Analizando estructura CSV...</span>
              </span>
            )}
            {dialectInfo && (
              <span
                data-testid="dialect-confidence-badge"
                className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                  dialectInfo.confidence_level === "Alta"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : dialectInfo.confidence_level === "Media"
                    ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                    : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                }`}
              >
                Confianza: {dialectInfo.confidence_level} ({Math.round(dialectInfo.confidence * 100)}%)
              </span>
            )}
          </div>

          {dialectInfo && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <span className="text-slate-400 block text-[10px]">Delimitador Detectado:</span>
                <span className="font-mono font-bold text-[#38BDF8]">
                  {dialectInfo.delimiter === "\t"
                    ? "Tabulación (\\t)"
                    : dialectInfo.delimiter === ";"
                    ? "Punto y coma (;)"
                    : dialectInfo.delimiter === "|"
                    ? "Pleca / Pipe (|)"
                    : "Coma (,)"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Encoding & Quoting:</span>
                <span className="text-slate-300">
                  {dialectInfo.encoding.toUpperCase()} (Quote: {dialectInfo.quote_char})
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Consistencia Estructural:</span>
                <span className="text-slate-300">
                  {Math.round(dialectInfo.consistency_score * 100)}% ({dialectInfo.col_count} columnas)
                </span>
              </div>
            </div>
          )}

          {dialectInfo?.is_ambiguous && (
            <div
              data-testid="dialect-ambiguity-warning"
              className="p-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-300 text-[11px]"
            >
              ⚠ {dialectInfo.ambiguity_warning}
            </div>
          )}

          {/* Manual Delimiter Override Control */}
          <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-slate-100 dark:border-slate-800">
            <span className="text-slate-400 text-[11px]">
              ¿El delimitador automático no es el correcto? Selecciona manualmente:
            </span>
            <select
              data-testid="manual-delimiter-select"
              value={manualDelimiter}
              onChange={(e) => setManualDelimiter(e.target.value)}
              className="px-2.5 py-1 rounded-lg border border-slate-300 dark:border-slate-700 dark:bg-[#0E1525] text-slate-800 dark:text-slate-200 text-xs focus:outline-none focus:border-[#38BDF8]"
            >
              <option value="">Usar Detección Automática</option>
              <option value=",">Coma ( , )</option>
              <option value=";">Punto y coma ( ; )</option>
              <option value="&#9;">Tabulación ( \t / TSV )</option>
              <option value="|">Pipe / Pleca ( | )</option>
            </select>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white">
        <span className="text-xs text-slate-500">
          Estrategia: <strong>Chunked Streaming Polars (50.000 filas por batch)</strong>
        </span>

        <button
          data-testid="start-stream-btn"
          disabled={!file || processing}
          onClick={handleStartStream}
          className="px-5 py-2 rounded-xl text-xs font-semibold bg-[#3B82F6] hover:bg-[#2563EB] disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center space-x-2 transition-all shadow-md shadow-[#3B82F6]/20"
        >
          {processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          <span>{processing ? "Procesando Chunks..." : "Iniciar Stream Normalización"}</span>
        </button>
      </div>

      {completed && downloadUrl && (
        <div
          data-testid="stream-completed-box"
          className="p-5 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-between text-xs"
        >
          <div className="flex items-center space-x-2 text-emerald-400 font-bold">
            <CheckCircle2 className="w-5 h-5" />
            <span>¡Stream parsing completado con éxito!</span>
          </div>

          <a
            data-testid="download-stream-result-btn"
            href={downloadUrl}
            download={fileName}
            className="px-4 py-2 rounded-xl font-semibold bg-emerald-500 hover:bg-emerald-600 text-white flex items-center space-x-1.5 shadow-sm"
          >
            <Download className="w-4 h-4" />
            <span>Descargar CSV Normalizado</span>
          </a>
        </div>
      )}
    </div>
  );
}
