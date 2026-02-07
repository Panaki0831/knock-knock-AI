"use client";

import { useEffect, useState } from "react";
import type { CalendarEntry, CalendarList } from "@/lib/api";
import { fetchCalendar, createCalendarEntry, triggerPipeline } from "@/lib/api";

export default function CalendarPage() {
  const [data, setData] = useState<CalendarList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = () => {
    fetchCalendar()
      .then(setData)
      .catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const handleTrigger = async (entryId: number) => {
    try {
      const result = await triggerPipeline(entryId);
      alert(`Pipeline triggered! Run ID: ${result.run_id}`);
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Content Calendar</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors"
        >
          + New Entry
        </button>
      </div>

      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-800 text-sm">
          Backend not connected. Start the server to manage the calendar.
        </div>
      )}

      {showForm && (
        <NewEntryForm
          onCreated={() => {
            setShowForm(false);
            load();
          }}
        />
      )}

      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left text-gray-500 border-b">
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Theme</th>
              <th className="px-4 py-3 font-medium">Category</th>
              <th className="px-4 py-3 font-medium">Funnel</th>
              <th className="px-4 py-3 font-medium">Platform</th>
              <th className="px-4 py-3 font-medium">Priority</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((entry) => (
              <tr key={entry.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-600">
                  {entry.scheduled_date}
                </td>
                <td className="px-4 py-3 font-medium max-w-xs truncate">
                  {entry.article_theme}
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {entry.category || "-"}
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {entry.funnel_stage || "-"}
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {entry.target_platform || "-"}
                </td>
                <td className="px-4 py-3">
                  <PriorityBadge priority={entry.priority} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={entry.status} />
                </td>
                <td className="px-4 py-3">
                  {entry.status === "scheduled" && (
                    <button
                      onClick={() => handleTrigger(entry.id)}
                      className="px-3 py-1 text-xs bg-brand-50 text-brand-700 rounded hover:bg-brand-100 font-medium"
                    >
                      Generate
                    </button>
                  )}
                  {entry.article_id && (
                    <span className="text-xs text-gray-400">
                      Article #{entry.article_id}
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {(!data || data.items.length === 0) && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                  No calendar entries. Click &quot;+ New Entry&quot; to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NewEntryForm({ onCreated }: { onCreated: () => void }) {
  const [theme, setTheme] = useState("");
  const [date, setDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [category, setCategory] = useState("");
  const [funnelStage, setFunnelStage] = useState("TOFU");
  const [platform, setPlatform] = useState("note");
  const [keywords, setKeywords] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createCalendarEntry({
        scheduled_date: date,
        article_theme: theme,
        target_keywords: keywords
          ? keywords.split(",").map((k) => k.trim())
          : null,
        category: category || null,
        funnel_stage: funnelStage,
        language: "ja",
        target_platform: platform,
        assigned_persona: null,
        priority: "medium",
        notes: null,
      });
      onCreated();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-xl shadow-sm border p-6 space-y-4"
    >
      <h3 className="font-semibold text-lg">New Calendar Entry</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="block">
          <span className="text-sm text-gray-600">Scheduled Date</span>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1 block w-full border rounded-lg px-3 py-2 text-sm"
            required
          />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">Article Theme</span>
          <input
            type="text"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            placeholder="e.g., AIバーチャルステージングの最新トレンド"
            className="mt-1 block w-full border rounded-lg px-3 py-2 text-sm"
            required
          />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">Category</span>
          <input
            type="text"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="e.g., 業界トレンド"
            className="mt-1 block w-full border rounded-lg px-3 py-2 text-sm"
          />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">Funnel Stage</span>
          <select
            value={funnelStage}
            onChange={(e) => setFunnelStage(e.target.value)}
            className="mt-1 block w-full border rounded-lg px-3 py-2 text-sm"
          >
            <option value="TOFU">TOFU (Awareness)</option>
            <option value="MOFU">MOFU (Consideration)</option>
            <option value="BOFU">BOFU (Decision)</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">Platform</span>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="mt-1 block w-full border rounded-lg px-3 py-2 text-sm"
          >
            <option value="note">note</option>
            <option value="medium">Medium</option>
            <option value="wordpress">WordPress</option>
            <option value="zenn">Zenn</option>
            <option value="hatena">Hatena Blog</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">
            Keywords (comma-separated)
          </span>
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="e.g., バーチャルステージング, AI, 不動産"
            className="mt-1 block w-full border rounded-lg px-3 py-2 text-sm"
          />
        </label>
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700"
        >
          Create Entry
        </button>
        <button
          type="button"
          onClick={onCreated}
          className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    scheduled: "bg-blue-100 text-blue-700",
    in_progress: "bg-yellow-100 text-yellow-700",
    completed: "bg-green-100 text-green-700",
    cancelled: "bg-gray-100 text-gray-600",
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

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    low: "bg-gray-100 text-gray-600",
    medium: "bg-blue-100 text-blue-600",
    high: "bg-orange-100 text-orange-700",
    urgent: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
        colors[priority] || "bg-gray-100 text-gray-600"
      }`}
    >
      {priority}
    </span>
  );
}
