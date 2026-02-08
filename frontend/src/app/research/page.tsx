"use client";

import { useEffect, useState } from "react";
import type { ResearchHistorySummary, ResearchHistoryDetail } from "@/lib/api";
import {
  fetchResearchHistory,
  fetchResearchHistoryDetail,
  deleteResearchHistory,
} from "@/lib/api";

export default function ResearchPage() {
  const [entries, setEntries] = useState<ResearchHistorySummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<ResearchHistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = async () => {
    try {
      const data = await fetchResearchHistory();
      setEntries(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleView = async (id: number) => {
    setDetailLoading(true);
    try {
      const data = await fetchResearchHistoryDetail(id);
      setDetail(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("この検索履歴を削除しますか？")) return;
    try {
      await deleteResearchHistory(id);
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const daysUntilExpiry = (expiresAt: string) => {
    const now = new Date();
    const exp = new Date(expiresAt);
    const diff = Math.ceil((exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return diff;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Research History</h1>
        <p className="text-sm text-gray-500 mt-1">
          過去のリサーチ結果を確認できます。1ヶ月経過で自動削除されます。
        </p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            Close
          </button>
        </div>
      )}

      {/* Entries List */}
      <div className="bg-white rounded-xl shadow-sm border">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">
            検索履歴 ({total})
          </h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : entries.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            検索履歴がまだありません。パイプラインを実行するとリサーチ結果が自動保存されます。
          </div>
        ) : (
          <div className="divide-y">
            {entries.map((entry) => {
              const days = daysUntilExpiry(entry.expires_at);
              return (
                <div key={entry.id} className="px-6 py-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-gray-900">
                        {entry.topic}
                      </h3>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {entry.target_keywords?.map((kw, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                      <div className="flex gap-4 mt-2 text-xs text-gray-400">
                        <span>Sources: {entry.source_count}</span>
                        <span>Statistics: {entry.stat_count}</span>
                        <span>
                          {new Date(entry.created_at).toLocaleDateString("ja-JP")}
                        </span>
                        <span
                          className={
                            days <= 7
                              ? "text-red-500 font-medium"
                              : "text-gray-400"
                          }
                        >
                          {days > 0
                            ? `${days}日後に期限切れ`
                            : "期限切れ"}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2 shrink-0 ml-4">
                      <button
                        onClick={() => handleView(entry.id)}
                        disabled={detailLoading}
                        className="px-3 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleDelete(entry.id)}
                        className="px-3 py-1 text-xs bg-gray-50 text-gray-500 rounded hover:bg-red-50 hover:text-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Research Detail Modal */}
      {detail && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-bold truncate pr-4">
                {detail.topic}
              </h3>
              <button
                onClick={() => setDetail(null)}
                className="px-3 py-1 text-sm bg-gray-100 text-gray-600 rounded hover:bg-gray-200 shrink-0"
              >
                Close
              </button>
            </div>
            <div className="overflow-y-auto px-6 py-4 space-y-6">
              {/* Research Report */}
              {detail.research_report && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">
                    Research Report
                  </h4>
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-800 bg-gray-50 p-4 rounded-lg">
                    {detail.research_report}
                  </pre>
                </div>
              )}

              {/* Key Statistics */}
              {detail.key_statistics && detail.key_statistics.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">
                    Key Statistics ({detail.key_statistics.length})
                  </h4>
                  <div className="space-y-2">
                    {detail.key_statistics.map((stat, i) => (
                      <div
                        key={i}
                        className="bg-gray-50 p-3 rounded-lg text-sm"
                      >
                        <p className="text-gray-800">{stat.stat}</p>
                        <div className="flex gap-4 mt-1 text-xs text-gray-400">
                          {stat.source && <span>Source: {stat.source}</span>}
                          {stat.date && <span>Date: {stat.date}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sources */}
              {detail.sources && detail.sources.length > 0 && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">
                    Sources ({detail.sources.length})
                  </h4>
                  <ul className="space-y-1 text-sm">
                    {detail.sources.map((src, i) => (
                      <li key={i} className="text-blue-600 truncate">
                        <a
                          href={src}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline"
                        >
                          {src}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Competitor Insights */}
              {detail.competitor_insights && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">
                    Competitor Insights
                  </h4>
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-800 bg-gray-50 p-4 rounded-lg">
                    {detail.competitor_insights}
                  </pre>
                </div>
              )}

              {/* Market Data */}
              {detail.market_data && (
                <div>
                  <h4 className="font-semibold text-gray-700 mb-2">
                    Market Data
                  </h4>
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-800 bg-gray-50 p-4 rounded-lg">
                    {detail.market_data}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
