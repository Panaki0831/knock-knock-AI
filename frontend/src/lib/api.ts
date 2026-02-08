/**
 * API client for the knock-knock-AI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_articles: number;
  articles_by_status: Record<string, number>;
  articles_this_month: number;
  pipeline_runs_today: number;
  pipeline_success_rate: number;
  avg_quality_scores: Record<string, number>;
  upcoming_calendar_entries: number;
  total_tokens_used: number;
  total_cost_usd: number;
}

export interface AgentStatus {
  agent_name: string;
  status: string;
  last_run_at: string | null;
  total_runs: number;
  avg_execution_time_seconds: number;
}

export interface DashboardOverview {
  stats: DashboardStats;
  agents: AgentStatus[];
  recent_articles: Record<string, any>[];
}

export function fetchDashboard(): Promise<DashboardOverview> {
  return apiFetch("/dashboard/overview");
}

// ── Articles ───────────────────────────────────────────────────────────────

export interface Article {
  id: number;
  title: string;
  slug: string;
  status: string;
  language: string;
  category: string | null;
  funnel_stage: string | null;
  target_keywords: string[] | null;
  meta_description: string | null;
  quality_scores: Record<string, number> | null;
  platform: string | null;
  published_url: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface ArticleList {
  items: Article[];
  total: number;
  page: number;
  page_size: number;
}

export function fetchArticles(params?: {
  page?: number;
  status?: string;
  language?: string;
}): Promise<ArticleList> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.status) qs.set("status", params.status);
  if (params?.language) qs.set("language", params.language);
  const query = qs.toString();
  return apiFetch(`/articles${query ? `?${query}` : ""}`);
}

export function fetchArticle(id: number): Promise<Article> {
  return apiFetch(`/articles/${id}`);
}

export function approveArticle(id: number): Promise<Article> {
  return apiFetch(`/articles/${id}/approve`, { method: "POST" });
}

export function rejectArticle(id: number): Promise<Article> {
  return apiFetch(`/articles/${id}/reject`, { method: "POST" });
}

export interface ArticleContent {
  id: number;
  title: string;
  content_markdown: string | null;
  content_html: string | null;
}

export function fetchArticleContent(id: number): Promise<ArticleContent> {
  return apiFetch(`/articles/${id}/content`);
}

export function deleteArticle(id: number): Promise<{ deleted: number }> {
  return apiFetch(`/articles/${id}`, { method: "DELETE" });
}

// ── Calendar ───────────────────────────────────────────────────────────────

export interface CalendarEntry {
  id: number;
  scheduled_date: string;
  article_theme: string;
  target_keywords: string[] | null;
  category: string | null;
  funnel_stage: string | null;
  language: string;
  target_platform: string | null;
  priority: string;
  status: string;
  article_id: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarList {
  items: CalendarEntry[];
  total: number;
}

export function fetchCalendar(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<CalendarList> {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.set("start_date", params.start_date);
  if (params?.end_date) qs.set("end_date", params.end_date);
  const query = qs.toString();
  return apiFetch(`/calendar${query ? `?${query}` : ""}`);
}

export function createCalendarEntry(
  data: Omit<CalendarEntry, "id" | "status" | "article_id" | "created_at" | "updated_at">
): Promise<CalendarEntry> {
  return apiFetch("/calendar", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Pipeline ───────────────────────────────────────────────────────────────

export interface PipelineRun {
  id: number;
  article_id: number | null;
  calendar_entry_id: number | null;
  topic: string | null;
  status: string;
  current_step: string | null;
  steps_log: Record<string, any>[] | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_tokens_used: number | null;
  total_cost_usd: number | null;
  created_at: string;
}

export function triggerPipeline(
  calendarEntryId: number
): Promise<{ run_id: number; status: string; message: string }> {
  return apiFetch("/pipeline/trigger", {
    method: "POST",
    body: JSON.stringify({ calendar_entry_id: calendarEntryId }),
  });
}

export function fetchPipelineRuns(): Promise<{
  items: PipelineRun[];
  total: number;
}> {
  return apiFetch("/pipeline/runs");
}

export function deleteFailedRuns(): Promise<{ deleted: number }> {
  return apiFetch("/pipeline/runs/failed", { method: "DELETE" });
}

export function deletePipelineRun(id: number): Promise<{ deleted: number }> {
  return apiFetch(`/pipeline/runs/${id}`, { method: "DELETE" });
}
