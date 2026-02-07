"use client";

import { useEffect, useState } from "react";
import type { DashboardOverview } from "@/lib/api";
import { fetchDashboard } from "@/lib/api";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-800">
          <p className="font-medium">Backend not connected</p>
          <p className="text-sm mt-1">
            Start the backend server to see live data. Showing placeholder UI.
          </p>
        </div>
        <PlaceholderDashboard />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 text-lg">Loading...</div>
      </div>
    );
  }

  const { stats, agents, recent_articles } = data;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Articles" value={stats.total_articles} />
        <StatCard title="This Month" value={stats.articles_this_month} />
        <StatCard
          title="Pipeline Success Rate"
          value={`${stats.pipeline_success_rate}%`}
        />
        <StatCard
          title="Total Cost"
          value={`$${stats.total_cost_usd.toFixed(2)}`}
        />
      </div>

      {/* Articles by Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h3 className="font-semibold text-lg mb-4">Articles by Status</h3>
          <div className="space-y-3">
            {Object.entries(stats.articles_by_status).map(([status, count]) => (
              <div key={status} className="flex justify-between items-center">
                <span className="capitalize text-sm text-gray-600">
                  {status}
                </span>
                <span className="font-mono font-semibold">{count}</span>
              </div>
            ))}
            {Object.keys(stats.articles_by_status).length === 0 && (
              <p className="text-sm text-gray-400">No articles yet</p>
            )}
          </div>
        </div>

        {/* Quality Scores */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h3 className="font-semibold text-lg mb-4">
            Average Quality Scores
          </h3>
          <div className="space-y-3">
            {Object.entries(stats.avg_quality_scores).map(([key, value]) => (
              <div key={key} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">
                    {key.replace(/_/g, " ").replace("score", "")}
                  </span>
                  <span className="font-mono font-semibold">{value}</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-brand-500 rounded-full h-2 transition-all"
                    style={{ width: `${value}%` }}
                  />
                </div>
              </div>
            ))}
            {Object.keys(stats.avg_quality_scores).length === 0 && (
              <p className="text-sm text-gray-400">No quality data yet</p>
            )}
          </div>
        </div>
      </div>

      {/* Agent Status */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h3 className="font-semibold text-lg mb-4">Agent Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {agents.map((agent) => (
            <div
              key={agent.agent_name}
              className="text-center p-3 rounded-lg bg-gray-50 border"
            >
              <div
                className={`inline-block w-2.5 h-2.5 rounded-full mb-2 ${
                  agent.status === "running"
                    ? "bg-green-400 animate-pulse"
                    : agent.status === "error"
                      ? "bg-red-400"
                      : "bg-gray-300"
                }`}
              />
              <p className="text-xs font-medium capitalize">
                {agent.agent_name}
              </p>
              <p className="text-[10px] text-gray-400 capitalize">
                {agent.status}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Articles */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h3 className="font-semibold text-lg mb-4">Recent Articles</h3>
        {recent_articles.length === 0 ? (
          <p className="text-sm text-gray-400">No articles yet</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2 font-medium">Title</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Language</th>
                <th className="pb-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {recent_articles.map((article) => (
                <tr key={article.id} className="border-b last:border-0">
                  <td className="py-2.5 font-medium">{article.title}</td>
                  <td className="py-2.5">
                    <StatusBadge status={article.status} />
                  </td>
                  <td className="py-2.5 uppercase text-gray-500">
                    {article.language}
                  </td>
                  <td className="py-2.5 text-gray-500">
                    {article.created_at
                      ? new Date(article.created_at).toLocaleDateString("ja-JP")
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
}: {
  title: string;
  value: string | number;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-5">
      <p className="text-sm text-gray-500 mb-1">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
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

function PlaceholderDashboard() {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Articles" value={0} />
        <StatCard title="This Month" value={0} />
        <StatCard title="Pipeline Success Rate" value="-%"/>
        <StatCard title="Total Cost" value="$0.00" />
      </div>

      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h3 className="font-semibold text-lg mb-4">Agent Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {[
            "orchestrator",
            "researcher",
            "planner",
            "writer",
            "editor",
            "localizer",
            "publisher",
          ].map((name) => (
            <div
              key={name}
              className="text-center p-3 rounded-lg bg-gray-50 border"
            >
              <div className="inline-block w-2.5 h-2.5 rounded-full mb-2 bg-gray-300" />
              <p className="text-xs font-medium capitalize">{name}</p>
              <p className="text-[10px] text-gray-400">idle</p>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
