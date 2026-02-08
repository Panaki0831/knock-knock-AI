"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  fetchArticleContent,
  fetchArticle,
  updateArticle,
  imageFileUrl,
} from "@/lib/api";
import type { Article, ArticleContent } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

type ViewMode = "edit" | "preview" | "split";

export default function ArticleEditorPage() {
  const params = useParams();
  const router = useRouter();
  const articleId = Number(params.id);

  const [article, setArticle] = useState<Article | null>(null);
  const [title, setTitle] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [metaDescription, setMetaDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("split");
  const [showMeta, setShowMeta] = useState(false);
  const editorRef = useRef<HTMLTextAreaElement>(null);

  // Load article data
  useEffect(() => {
    if (!articleId) return;
    Promise.all([fetchArticle(articleId), fetchArticleContent(articleId)])
      .then(([articleData, contentData]) => {
        setArticle(articleData);
        setTitle(articleData.title);
        setMetaDescription(articleData.meta_description || "");
        setKeywords(
          articleData.target_keywords
            ? articleData.target_keywords.join(", ")
            : ""
        );
        setMarkdown(contentData.content_markdown || "");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [articleId]);

  // Save article
  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const keywordList = keywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
      await updateArticle(articleId, {
        title,
        content_markdown: markdown,
        meta_description: metaDescription || undefined,
        target_keywords: keywordList.length > 0 ? keywordList : undefined,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }, [articleId, title, markdown, metaDescription, keywords]);

  // Keyboard shortcut: Ctrl+S / Cmd+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleSave]);

  // Toolbar actions for inserting markdown formatting
  const insertAtCursor = (before: string, after: string = "") => {
    const textarea = editorRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = markdown.substring(start, end);
    const newText =
      markdown.substring(0, start) +
      before +
      selected +
      after +
      markdown.substring(end);
    setMarkdown(newText);
    // Restore cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(
        start + before.length,
        start + before.length + selected.length
      );
    }, 0);
  };

  // Render markdown to HTML-like display with images
  const renderPreview = (md: string) => {
    let html = md;

    // Images: ![alt](url)
    html = html.replace(
      /!\[([^\]]*)\]\(([^)]+)\)/g,
      (_, alt, src) => {
        // Resolve relative API paths
        const fullSrc = src.startsWith("/api/")
          ? `${API_BASE.replace("/api/v1", "")}${src}`
          : src;
        return `<img src="${fullSrc}" alt="${alt}" class="article-img" />`;
      }
    );

    // H1
    html = html.replace(
      /^# (.+)$/gm,
      '<h1 class="preview-h1">$1</h1>'
    );
    // H3 before H2
    html = html.replace(
      /^### (.+)$/gm,
      '<h3 class="preview-h3">$1</h3>'
    );
    // H2
    html = html.replace(
      /^## (.+)$/gm,
      '<h2 class="preview-h2">$1</h2>'
    );
    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Italic
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    // Links
    html = html.replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" class="preview-link" target="_blank" rel="noopener">$1</a>'
    );
    // Unordered lists
    html = html.replace(/^- (.+)$/gm, '<li class="preview-li">$1</li>');
    html = html.replace(
      /(<li class="preview-li">.*<\/li>\n?)+/g,
      (match) => `<ul class="preview-ul">${match}</ul>`
    );
    // Ordered lists
    html = html.replace(
      /^\d+\. (.+)$/gm,
      '<li class="preview-oli">$1</li>'
    );
    // Blockquotes
    html = html.replace(
      /^> (.+)$/gm,
      '<blockquote class="preview-bq">$1</blockquote>'
    );
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code class="preview-code">$1</code>');
    // Horizontal rules
    html = html.replace(/^---$/gm, '<hr class="preview-hr" />');
    // Paragraphs (double newline)
    html = html.replace(/\n\n/g, '</p><p class="preview-p">');
    html = `<p class="preview-p">${html}</p>`;
    // Clean up empty paragraphs
    html = html.replace(/<p class="preview-p"><\/p>/g, "");
    html = html.replace(
      /<p class="preview-p">(<h[123]|<ul|<blockquote|<hr|<img)/g,
      "$1"
    );
    html = html.replace(
      /(<\/h[123]>|<\/ul>|<\/blockquote>|<\/hr>)<\/p>/g,
      "$1"
    );

    return html;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="text-gray-400">Loading editor...</div>
      </div>
    );
  }

  if (error && !article) {
    return (
      <div className="p-8">
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
        <button
          onClick={() => router.push("/articles")}
          className="mt-4 px-4 py-2 bg-gray-100 rounded-lg text-sm"
        >
          Back to Articles
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)]">
      {/* Top Bar */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/articles")}
            className="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200"
          >
            Back
          </button>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">#{articleId}</span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                article?.status === "reviewing"
                  ? "bg-yellow-100 text-yellow-700"
                  : article?.status === "approved"
                    ? "bg-blue-100 text-blue-700"
                    : article?.status === "published"
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-600"
              }`}
            >
              {article?.status}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex gap-0.5 bg-gray-100 rounded-lg p-0.5">
            {(["edit", "split", "preview"] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1 text-xs rounded-md font-medium ${
                  viewMode === mode
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {mode === "edit"
                  ? "Editor"
                  : mode === "preview"
                    ? "Preview"
                    : "Split"}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowMeta(!showMeta)}
            className="px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200"
          >
            {showMeta ? "Hide Meta" : "Meta"}
          </button>

          {/* Save button */}
          <button
            onClick={handleSave}
            disabled={saving}
            className={`px-4 py-1.5 text-sm font-medium rounded-lg ${
              saved
                ? "bg-green-600 text-white"
                : "bg-blue-600 text-white hover:bg-blue-700"
            } disabled:opacity-50`}
          >
            {saving ? "Saving..." : saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>

      {/* Error bar */}
      {error && (
        <div className="bg-red-50 text-red-700 px-4 py-2 text-sm border-b shrink-0">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            Close
          </button>
        </div>
      )}

      {/* Title input */}
      <div className="bg-white border-b px-4 py-3 shrink-0">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Article title..."
          className="w-full text-2xl font-bold text-gray-900 outline-none placeholder:text-gray-300"
        />
      </div>

      {/* Meta panel (collapsible) */}
      {showMeta && (
        <div className="bg-gray-50 border-b px-4 py-3 shrink-0 grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Meta Description
            </label>
            <textarea
              value={metaDescription}
              onChange={(e) => setMetaDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border rounded-lg text-sm resize-none"
              placeholder="SEO meta description..."
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Target Keywords (comma separated)
            </label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm"
              placeholder="keyword1, keyword2, keyword3"
            />
          </div>
        </div>
      )}

      {/* Toolbar */}
      {(viewMode === "edit" || viewMode === "split") && (
        <div className="bg-white border-b px-4 py-1.5 flex gap-1 shrink-0">
          <button
            onClick={() => insertAtCursor("**", "**")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100 font-bold"
            title="Bold"
          >
            B
          </button>
          <button
            onClick={() => insertAtCursor("*", "*")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100 italic"
            title="Italic"
          >
            I
          </button>
          <div className="w-px bg-gray-200 mx-1" />
          <button
            onClick={() => insertAtCursor("## ")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100"
            title="Heading 2"
          >
            H2
          </button>
          <button
            onClick={() => insertAtCursor("### ")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100"
            title="Heading 3"
          >
            H3
          </button>
          <div className="w-px bg-gray-200 mx-1" />
          <button
            onClick={() => insertAtCursor("- ")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100"
            title="Bullet list"
          >
            List
          </button>
          <button
            onClick={() => insertAtCursor("> ")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100"
            title="Blockquote"
          >
            Quote
          </button>
          <button
            onClick={() => insertAtCursor("[", "](url)")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100"
            title="Link"
          >
            Link
          </button>
          <button
            onClick={() => insertAtCursor("![alt](", ")")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100"
            title="Image"
          >
            Image
          </button>
          <button
            onClick={() => insertAtCursor("`", "`")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100 font-mono"
            title="Inline code"
          >
            Code
          </button>
          <button
            onClick={() => insertAtCursor("\n---\n")}
            className="px-2 py-1 text-xs bg-gray-50 rounded hover:bg-gray-100"
            title="Horizontal rule"
          >
            HR
          </button>
          <div className="flex-1" />
          <span className="text-xs text-gray-400 self-center">
            Ctrl+S to save
          </span>
        </div>
      )}

      {/* Editor / Preview area */}
      <div className="flex-1 overflow-hidden flex">
        {/* Editor pane */}
        {(viewMode === "edit" || viewMode === "split") && (
          <div
            className={`${
              viewMode === "split" ? "w-1/2 border-r" : "w-full"
            } flex flex-col`}
          >
            <textarea
              ref={editorRef}
              value={markdown}
              onChange={(e) => setMarkdown(e.target.value)}
              className="flex-1 w-full p-4 font-mono text-sm leading-relaxed resize-none outline-none bg-gray-50 text-gray-800"
              placeholder="Write your article in Markdown..."
              spellCheck={false}
            />
          </div>
        )}

        {/* Preview pane */}
        {(viewMode === "preview" || viewMode === "split") && (
          <div
            className={`${
              viewMode === "split" ? "w-1/2" : "w-full"
            } overflow-y-auto bg-white`}
          >
            <div className="max-w-3xl mx-auto px-8 py-6">
              <style
                dangerouslySetInnerHTML={{
                  __html: `
                .preview-h1 { font-size: 2rem; font-weight: 800; margin: 0 0 1.5rem 0; color: #111; line-height: 1.2; }
                .preview-h2 { font-size: 1.5rem; font-weight: 700; margin: 2rem 0 0.75rem 0; color: #222; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
                .preview-h3 { font-size: 1.2rem; font-weight: 600; margin: 1.5rem 0 0.5rem 0; color: #333; }
                .preview-p { margin: 0.75rem 0; line-height: 1.8; color: #374151; font-size: 0.95rem; }
                .preview-link { color: #2563eb; text-decoration: underline; }
                .preview-ul { margin: 0.5rem 0; padding-left: 1.5rem; list-style: disc; }
                .preview-li { margin: 0.25rem 0; line-height: 1.6; color: #374151; }
                .preview-oli { margin: 0.25rem 0; line-height: 1.6; color: #374151; }
                .preview-bq { border-left: 4px solid #d1d5db; padding: 0.5rem 1rem; margin: 1rem 0; color: #6b7280; background: #f9fafb; border-radius: 0 0.5rem 0.5rem 0; }
                .preview-code { background: #f3f4f6; padding: 0.15rem 0.4rem; border-radius: 0.25rem; font-size: 0.85em; font-family: monospace; color: #dc2626; }
                .preview-hr { border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }
                .article-img { max-width: 100%; height: auto; border-radius: 0.75rem; margin: 1.5rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
              `,
                }}
              />
              <div
                dangerouslySetInnerHTML={{
                  __html: renderPreview(markdown),
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
