import React, { useState, useRef } from "react";
import { UploadCloud, FileSpreadsheet, Loader2, Sparkles, AlertCircle } from "lucide-react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function DropZone({ t, onAnalysisComplete }) {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = async (file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["csv", "xlsx", "xls"].includes(ext)) {
      setError(t.upload.error_format);
      return;
    }
    setError(null);
    setLoading(true);
    setLoadingMessage(t.upload.uploading);

    try {
      const formData = new FormData();
      formData.append("file", file);

      // Step 1: Upload
      const uploadRes = await axios.post(`${BACKEND_URL}/api/files/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        withCredentials: true
      });

      const fileId = uploadRes.data.file_id;
      const defaultSheet = uploadRes.data.default_sheet;

      // Step 2: Analyze
      setLoadingMessage(t.upload.analyzing);
      const analyzeRes = await axios.get(`${BACKEND_URL}/api/files/${fileId}/analyze?sheet=${encodeURIComponent(defaultSheet)}`, {
        withCredentials: true
      });

      onAnalysisComplete({
        fileInfo: uploadRes.data,
        analysisData: analyzeRes.data
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Error al procesar el archivo. Revisa el formato.");
    } finally {
      setLoading(false);
    }
  };

  const loadSample = async (sampleType) => {
    setLoading(true);
    setLoadingMessage(t.upload.analyzing);
    setError(null);

    try {
      const sampleRes = await axios.get(`${BACKEND_URL}/api/samples/${sampleType}`);
      const fileId = sampleRes.data.file_id;

      const analyzeRes = await axios.get(`${BACKEND_URL}/api/files/${fileId}/analyze?sheet=Sheet1`, {
        withCredentials: true
      });

      onAnalysisComplete({
        fileInfo: sampleRes.data,
        analysisData: analyzeRes.data
      });
    } catch (err) {
      setError("No se pudo cargar el dataset de prueba.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Drop Zone Box */}
      <div
        data-testid="upload-dropzone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !loading && fileInputRef.current.click()}
        className={`relative border-2 border-dashed rounded-2xl p-10 sm:p-14 text-center cursor-pointer transition-all duration-200 ${
          isDragging
            ? "border-[#38BDF8] bg-[#3B82F6]/10 scale-[1.01]"
            : "border-slate-300 dark:border-slate-800 hover:border-[#3B82F6]/60 dark:bg-[#0B1220]/70 bg-white/60 hover:shadow-lg hover:shadow-[#38BDF8]/5"
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          accept=".csv,.xlsx,.xls"
          className="hidden"
          data-testid="file-input-hidden"
        />

        {loading ? (
          <div className="flex flex-col items-center justify-center space-y-4">
            <Loader2 className="w-12 h-12 text-[#38BDF8] animate-spin" />
            <p className="text-base font-medium text-slate-700 dark:text-slate-300">{loadingMessage}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#3B82F6]/20 to-[#38BDF8]/20 flex items-center justify-center border border-[#3B82F6]/30">
              <UploadCloud className="w-8 h-8 text-[#38BDF8]" />
            </div>
            <div>
              <h3 className="text-xl font-bold dark:text-white text-slate-900">{t.upload.drop_title}</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{t.upload.drop_subtitle}</p>
            </div>
            <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              {t.upload.supported_formats}
            </span>
          </div>
        )}
      </div>

      {error && (
        <div
          data-testid="upload-error-alert"
          className="p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-500 flex items-center space-x-3 text-sm"
        >
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Pre-Loaded Realistic Messy Sample Datasets */}
      <div className="pt-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3 text-center">
          {t.upload.sample_title}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            data-testid="sample-erp-button"
            onClick={() => loadSample("erp")}
            disabled={loading}
            className="p-3 text-left rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white hover:border-[#3B82F6]/50 hover:shadow-md transition-all group"
          >
            <div className="flex items-center space-x-2 text-xs font-bold text-[#38BDF8]">
              <FileSpreadsheet className="w-4 h-4" />
              <span>ERP Ventas</span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-snug">
              Banners de título, decimales europeos (1.250,50) y fechas mezcladas.
            </p>
          </button>

          <button
            data-testid="sample-bank-button"
            onClick={() => loadSample("bank")}
            disabled={loading}
            className="p-3 text-left rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white hover:border-[#3B82F6]/50 hover:shadow-md transition-all group"
          >
            <div className="flex items-center space-x-2 text-xs font-bold text-[#38BDF8]">
              <FileSpreadsheet className="w-4 h-4" />
              <span>Extracto Bancario</span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-snug">
              Cabecera IBAN, saltos vacíos y formato de importes con signo.
            </p>
          </button>

          <button
            data-testid="sample-crm-button"
            onClick={() => loadSample("crm")}
            disabled={loading}
            className="p-3 text-left rounded-xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white hover:border-[#3B82F6]/50 hover:shadow-md transition-all group"
          >
            <div className="flex items-center space-x-2 text-xs font-bold text-[#38BDF8]">
              <FileSpreadsheet className="w-4 h-4" />
              <span>Leads CRM</span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-snug">
              Columnas completamente vacías, filas vacías intermedias y fechas dispares.
            </p>
          </button>
        </div>
      </div>
    </div>
  );
}
