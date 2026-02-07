"use client";

import { useEffect, useState } from "react";
import type { Article, ArticleList } from "@/lib/api";
import { fetchArticles, approveArticle, rejectArticle } from "@/lib/api";

export default function ArticlesPage() {
  const [data, setData] = useState<ArticleList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  const load = () => {
    fetchArticles({ page, status: statusFilter || undefined })
      .then(setData)
      .catch((e) => setError(e.message));
  };

  useEffect(load, [page, statusFilter]);

  const handleApprove = async (id: number) => {
    await approveArticle(id);
    load();
  };

  const handleReject = async (id: number) => {
    await rejectArticle(id);
    load();
  };

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
              <tr key={article.id} className="border-b last:border-0 hover:bg-gray-50">
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
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
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
              Page {data.page} of {Math.ceil(data.total / data.page_size)} ({data.total} total)
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
