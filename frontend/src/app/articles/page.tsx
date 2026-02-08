"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Article, ArticleList, ArticleContent, PipelineRun } from "@/lib/api";
import {
  fetchArticles,
  approveArticle,
  rejectArticle,
  fetchArticleContent,
  deleteArticle,
  fetchPipelineRuns,
  deleteFailedRuns,
  deletePipelineRun,
} from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export default function ArticlesPage() {
  const [data, setData] = useState<ArticleList | null>(null);
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const [previewContent, setPreviewContent] = useState<ArticleContent | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // "generating" and "failed" are pipeline-run filters, not article statuses
  const isPipelineFilter = statusFilter === "generating" || statusFilter === "failed";

  const load = () => {
    fetchArticles({ page, status: isPipelineFilter ? undefined : statusFilter || undefined })
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

  const handlePreview = async (id: number) => {
    setPreviewLoading(true);
    try {
      const content = await fetchArticleContent(id);
      setPreviewContent(content);
    } catch {
      setError("Failed to load article content");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDeleteArticle = async (id: number) => {
    if (!confirm("この記事を削除しますか？")) return;
    await deleteArticle(id);
    load();
  };

  const handleDeleteRun = async (id: number) => {
    if (!confirm("このパイプライン実行を削除しますか？")) return;
    await deletePipelineRun(id);
    load();
  };

  // Filter pipeline runs: show active runs + only the 3 most recent failures
  const activeInProgress = pipelineRuns.filter(
    (r) => r.status === "pending" || r.status === "running"
  );
  const recentFailed = pipelineRuns
    .filter((r) => r.status === "failed")
    .slice(0, 3); // Only last 3 failures (already sorted by created_at DESC)
  const activeRuns = [...activeInProgress, ...recentFailed];

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
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
              Pipeline Runs
            </h3>
            {recentFailed.length > 0 && (
              <button
                onClick={async () => {
                  await deleteFailedRuns();
                  load();
                }}
                className="px-3 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
              >
                Clear Failed Runs
              </button>
            )}
          </div>
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
                      {(run.status === "pending" || run.status === "running") && (
                        <StepProgressBar currentStep={run.current_step} />
                      )}
                      {(run.status === "pending" || run.status === "running") && (
                        <span className="inline-block w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">
                        {new Date(run.created_at).toLocaleDateString("ja-JP")}{" "}
                        {new Date(run.created_at).toLocaleTimeString("ja-JP")}
                      </span>
                      {run.status === "failed" && (
                        <>
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
                          <button
                            onClick={() => handleDeleteRun(run.id)}
                            className="px-2 py-1 text-xs bg-gray-50 text-gray-500 rounded hover:bg-red-50 hover:text-red-600"
                            title="Delete run"
                          >
                            🗑
                          </button>
                        </>
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

      {/* Article Content Preview Modal */}
      {previewContent && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-bold truncate pr-4">
                {previewContent.title}
              </h3>
              <div className="flex items-center gap-2 shrink-0">
                <Link
                  href={`/articles/${previewContent.id}/edit`}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Edit
                </Link>
                <button
                  onClick={() => setPreviewContent(null)}
                  className="px-3 py-1 text-sm bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="overflow-y-auto px-6 py-4">
              {previewContent.content_markdown ? (
                <>
                  <style dangerouslySetInnerHTML={{ __html: `
                    .pv-h1 { font-size: 2rem; font-weight: 800; margin: 0 0 1.5rem 0; color: #111; line-height: 1.2; }
                    .pv-h2 { font-size: 1.5rem; font-weight: 700; margin: 2rem 0 0.75rem 0; color: #222; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
                    .pv-h3 { font-size: 1.2rem; font-weight: 600; margin: 1.5rem 0 0.5rem 0; color: #333; }
                    .pv-p { margin: 0.75rem 0; line-height: 1.8; color: #374151; font-size: 0.95rem; }
                    .pv-link { color: #2563eb; text-decoration: underline; }
                    .pv-ul { margin: 0.5rem 0; padding-left: 1.5rem; list-style: disc; }
                    .pv-li { margin: 0.25rem 0; line-height: 1.6; color: #374151; }
                    .pv-bq { border-left: 4px solid #d1d5db; padding: 0.5rem 1rem; margin: 1rem 0; color: #6b7280; background: #f9fafb; border-radius: 0 0.5rem 0.5rem 0; }
                    .pv-code { background: #f3f4f6; padding: 0.15rem 0.4rem; border-radius: 0.25rem; font-size: 0.85em; font-family: monospace; color: #dc2626; }
                    .pv-hr { border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }
                    .pv-img { max-width: 100%; height: auto; border-radius: 0.75rem; margin: 1.5rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
                  ` }} />
                  <div
                    className="max-w-3xl mx-auto"
                    dangerouslySetInnerHTML={{
                      __html: renderMarkdownPreview(previewContent.content_markdown),
                    }}
                  />
                </>
              ) : (
                <p className="text-gray-400 text-center py-8">
                  No content available
                </p>
              )}
            </div>
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
                      <button
                        onClick={() => handlePreview(article.id)}
                        className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
                        disabled={previewLoading}
                      >
                        View
                      </button>
                      <Link
                        href={`/articles/${article.id}/edit`}
                        className="px-2 py-1 text-xs bg-purple-50 text-purple-700 rounded hover:bg-purple-100"
                      >
                        Edit
                      </Link>
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
                      {(article.status === "rejected" || article.status === "drafting") && (
                        <button
                          onClick={() => handleDeleteArticle(article.id)}
                          className="px-2 py-1 text-xs bg-gray-50 text-gray-500 rounded hover:bg-red-50 hover:text-red-600"
                          title="Delete article"
                        >
                          🗑
                        </button>
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

const STEP_LABELS: Record<string, string> = {
  queued: "Queued",
  research: "Research",
  plan: "Planning",
  write: "Writing",
  edit: "Editing",
  image_generate: "Images",
  localize: "Localizing",
  publish: "Publishing",
};

const STEP_ORDER = ["research", "plan", "write", "edit", "image_generate", "publish"];

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

function StepProgressBar({ currentStep }: { currentStep: string | null }) {
  if (!currentStep || currentStep === "queued") return null;
  const currentIdx = STEP_ORDER.indexOf(currentStep);
  if (currentIdx < 0) return null;

  return (
    <div className="flex items-center gap-1">
      {STEP_ORDER.map((step, idx) => (
        <div key={step} className="flex items-center gap-1">
          <div
            className={`w-2 h-2 rounded-full ${
              idx < currentIdx
                ? "bg-green-500"
                : idx === currentIdx
                  ? "bg-yellow-500 animate-pulse"
                  : "bg-gray-200"
            }`}
            title={STEP_LABELS[step] || step}
          />
          {idx < STEP_ORDER.length - 1 && (
            <div
              className={`w-3 h-0.5 ${
                idx < currentIdx ? "bg-green-300" : "bg-gray-200"
              }`}
            />
          )}
        </div>
      ))}
      <span className="ml-1 text-xs text-gray-500">
        {STEP_LABELS[currentStep] || currentStep}
      </span>
    </div>
  );
}

function renderMarkdownPreview(md: string): string {
  let html = md;

  // Images: ![alt](url)
  html = html.replace(
    /!\[([^\]]*)\]\(([^)]+)\)/g,
    (_, alt, src) => {
      const fullSrc = src.startsWith("/api/")
        ? `${API_BASE.replace("/api/v1", "")}${src}`
        : src;
      return `<img src="${fullSrc}" alt="${alt}" class="pv-img" />`;
    }
  );

  // H1
  html = html.replace(/^# (.+)$/gm, '<h1 class="pv-h1">$1</h1>');
  // H3 before H2
  html = html.replace(/^### (.+)$/gm, '<h3 class="pv-h3">$1</h3>');
  // H2
  html = html.replace(/^## (.+)$/gm, '<h2 class="pv-h2">$1</h2>');
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Links
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" class="pv-link" target="_blank" rel="noopener">$1</a>'
  );
  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li class="pv-li">$1</li>');
  html = html.replace(
    /(<li class="pv-li">.*<\/li>\n?)+/g,
    (match) => `<ul class="pv-ul">${match}</ul>`
  );
  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="pv-li">$1</li>');
  // Blockquotes
  html = html.replace(
    /^> (.+)$/gm,
    '<blockquote class="pv-bq">$1</blockquote>'
  );
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="pv-code">$1</code>');
  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr class="pv-hr" />');
  // Paragraphs
  html = html.replace(/\n\n/g, '</p><p class="pv-p">');
  html = `<p class="pv-p">${html}</p>`;
  // Clean up empty paragraphs
  html = html.replace(/<p class="pv-p"><\/p>/g, "");
  html = html.replace(
    /<p class="pv-p">(<h[123]|<ul|<blockquote|<hr|<img)/g,
    "$1"
  );
  html = html.replace(
    /(<\/h[123]>|<\/ul>|<\/blockquote>|<\/hr>)<\/p>/g,
    "$1"
  );

  return html;
}
