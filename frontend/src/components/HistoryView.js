import React, { useState, useEffect } from "react";
import { History as HistoryIcon, Clock, CheckCircle2, FileText, Loader2 } from "lucide-react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

export default function HistoryView({ t }) {
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/executions`, { withCredentials: true });
      setExecutions(res.data || []);
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 flex justify-center items-center">
        <Loader2 className="w-8 h-8 text-[#38BDF8] animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-bold dark:text-white text-slate-900 flex items-center gap-2">
          <HistoryIcon className="w-5 h-5 text-[#38BDF8]" />
          <span>{t.history_view.title}</span>
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Auditoría de ejecuciones realizadas con CleanSheet.
        </p>
      </div>

      {executions.length === 0 ? (
        <div
          data-testid="history-empty-state"
          className="p-12 text-center rounded-2xl border border-slate-200 dark:border-slate-800 dark:bg-[#0B1220] bg-white space-y-3"
        >
          <Clock className="w-12 h-12 text-slate-400 mx-auto opacity-50" />
          <h4 className="text-base font-bold dark:text-white text-slate-800">
            {t.history_view.empty_title}
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">{t.history_view.empty_desc}</p>
        </div>
      ) : (
        <div
          data-testid="history-table-container"
          className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-white dark:bg-[#0B1220]"
        >
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50 dark:bg-[#0E1525] border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3">{t.history_view.col_date}</th>
                <th className="px-4 py-3">{t.history_view.col_file}</th>
                <th className="px-4 py-3">{t.history_view.col_rows}</th>
                <th className="px-4 py-3">{t.history_view.col_transformations}</th>
                <th className="px-4 py-3">{t.history_view.col_duration}</th>
                <th className="px-4 py-3">{t.history_view.col_status}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
              {executions.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-medium dark:text-slate-200 text-slate-800 flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-[#38BDF8]" />
                    <span>{item.file_name || "Archivo"}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                    {item.rows_input} → {item.rows_output}
                  </td>
                  <td className="px-4 py-3 text-[#38BDF8] font-semibold">
                    {item.transformations_count}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{item.duration_ms} ms</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>{item.status}</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
