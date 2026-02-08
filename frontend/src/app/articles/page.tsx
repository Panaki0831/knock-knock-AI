"use client";

import { useEffect, useState } from "react";
import type { Article, ArticleList, PipelineRun } from "@/lib/api";
import {
  fetchArticles,
  approveArticle,
  rejectArticle,
  fetchPipelineRuns,
} from "@/lib/api";

export default function ArticlesPage() {
  const [data, setData] = useState<ArticleList | null>(null);
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);

  const load = () => {
    fetchArticles({ page, status: statusFilter || undefined })
      .then(setData)
      .catch((e) => setError(e.message));

    fetchPipelineRuns()
      .then((res) => setPipelineRuns(res.items))
      .catch(() => {});
  };

  useEffect(load, [page, statusFilter]);

  // Auto-refresh when there are active pipeline runs
  useEffect(() => {
    const hasActive = pipelineRuns.some(
      (r) => r.status === "pending" || r.status === "running"
    );
    if (!hasActive) return;
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [pipelineRuns]);

  const handleApprove = async (id: number) => {
    await approveArticle(id);
    load();
  };

  const handleReject = async (id: number) => {
    await rejectArticle(id);
    load();
  };

  // Filter pipeline runs: show only in-progress or failed (not completed ones that already have an article)
  const activeRuns = pipelineRuns.filter(
    (r) =>
      r.status === "pending" ||
      r.status === "running" ||
      r.status === "failed"
  );

  const showActiveRuns =
    !statusFilter ||
    statusFilter === "generating" ||
    (statusFilter === "failed" && activeRuns.some((r) => r.status === "failed"));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Articles</h2>
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="text-sm border rounded-lg px-3 py-2 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="generating">Generating</option>
            <option value="failed">Failed</option>
            <option value="drafting">Drafting</option>
            <option value="reviewing">Reviewing</option>
            <option value="approved">Approved</option>
            <option value="published">Published</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-800 text-sm">
          Backend not connected. Start the server to see articles.
        </div>
      )}

      {/* Active Pipeline Runs Section */}
      {showActiveRuns && activeRuns.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Pipeline Runs
          </h3>
          <div className="space-y-2">
            {activeRuns
              .filter((r) =>
                statusFilter === "failed"
                  ? r.status === "failed"
                  : statusFilter === "generating"
                    ? r.status === "pending" || r.status === "running"
                    : true
              )
              .map((run) => (
                <div
                  key={`run-${run.id}`}
                  className={`bg-white rounded-xl shadow-sm border overflow-hidden ${
                    run.status === "failed" ? "border-red-200" : ""
                  }`}
                >
                  <div className="px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-gray-400 text-sm">
                        Run #{run.id}
                      </span>
                      <span className="font-medium text-sm">
                        {run.topic || "Untitled"}
                      </span>
                      <PipelineStatusBadge status={run.status} />
                      {(run.status === "pending" || run.status === "running") &&
                        run.current_step && (
                          <span className="text-xs text-gray-400">
                            Step: {run.current_step}
                          </span>
                        )}
                      {(run.status === "pending" || run.status === "running") && (
                        <span className="inline-block w-4 h-4 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">
                        {new Date(run.created_at).toLocaleDateString("ja-JP")}{" "}
                        {new Date(run.created_at).toLocaleTimeString("ja-JP")}
                      </span>
                      {run.status === "failed" && (
                        <button
                          onClick={() =>
                            setExpandedRunId(
                              expandedRunId === run.id ? null : run.id
                            )
                          }
                          className="px-2 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100"
                        >
                          {expandedRunId === run.id
                            ? "Hide Log"
                            : "Show Log"}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Expandable failure log */}
                  {expandedRunId === run.id && run.status === "failed" && (
                    <div className="border-t bg-gray-50 px-4 py-3 space-y-3">
                      {run.error_message && (
                        <div>
                          <p className="text-xs font-semibold text-red-600 mb-1">
                            Error Message
                          </p>
                          <pre className="text-xs bg-red-50 border border-red-200 rounded p-3 whitespace-pre-wrap text-red-800 max-h-40 overflow-y-auto">
                            {run.error_message}
                          </pre>
                        </div>
                      )}
                      {run.steps_log && run.steps_log.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-gray-600 mb-1">
                            Steps Log
                          </p>
                          <div className="space-y-1">
                            {run.steps_log.map((step, idx) => (
                              <div
                                key={idx}
                                className={`text-xs rounded p-2 border ${
                                  step.status === "failed"
                                    ? "bg-red-50 border-red-200 text-red-700"
                                    : step.status === "completed"
                                      ? "bg-green-50 border-green-200 text-green-700"
                                      : "bg-gray-50 border-gray-200 text-gray-600"
                                }`}
                              >
                                <span className="font-medium">
                                  {step.step || step.name || `Step ${idx + 1}`}
                                </span>
                                {" - "}
                                <span>{step.status || "unknown"}</span>
                                {step.error && (
                                  <p className="mt-1 text-red-600">
                                    {step.error}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {!run.error_message &&
                        (!run.steps_log || run.steps_log.length === 0) && (
                          <p className="text-xs text-gray-400">
                            No detailed logs available.
                          </p>
                        )}
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Articles Table */}
      {(!statusFilter ||
        (statusFilter !== "generating" && statusFilter !== "failed")) && (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-gray-500 border-b">
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Language</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Funnel</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((article) => (
                <tr
                  key={article.id}
                  className="border-b last:border-0 hover:bg-gray-50"
                >
                  <td className="px-4 py-3 text-gray-400">#{article.id}</td>
                  <td className="px-4 py-3 font-medium max-w-xs truncate">
                    {article.title}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={article.status} />
                  </td>
                  <td className="px-4 py-3 uppercase text-gray-500">
                    {article.language}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {article.category || "-"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {article.funnel_stage || "-"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(article.created_at).toLocaleDateString("ja-JP")}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      {article.status === "reviewing" && (
                        <>
                          <button
                            onClick={() => handleApprove(article.id)}
                            className="px-2 py-1 text-xs bg-green-50 text-green-700 rounded hover:bg-green-100"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(article.id)}
                            className="px-2 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {(!data || data.items.length === 0) && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-4 py-8 text-center text-gray-400"
                  >
                    No articles found
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Pagination */}
          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
              <p className="text-xs text-gray-500">
                Page {data.page} of{" "}
                {Math.ceil(data.total / data.page_size)} ({data.total} total)
              </p>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1 text-xs border rounded disabled:opacity-50"
                >
                  Prev
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= Math.ceil(data.total / data.page_size)}
                  className="px-3 py-1 text-xs border rounded disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    drafting: "bg-gray-100 text-gray-600",
    reviewing: "bg-yellow-100 text-yellow-700",
    approved: "bg-blue-100 text-blue-700",
    published: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
        colors[status] || "bg-gray-100 text-gray-600"
      }`}
    >
      {status}
    </span>
  );
}

function PipelineStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-blue-100 text-blue-700",
    running: "bg-yellow-100 text-yellow-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  const labels: Record<string, string> = {
    pending: "queued",
    running: "generating",
    completed: "completed",
    failed: "failed",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
        colors[status] || "bg-gray-100 text-gray-600"
      }`}
    >
      {labels[status] || status}
    </span>
  );
}
