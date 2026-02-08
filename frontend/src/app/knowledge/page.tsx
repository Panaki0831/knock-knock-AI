"use client";

import { useEffect, useState, useRef } from "react";
import type { KnowledgeDocument, KnowledgeDocumentContent } from "@/lib/api";
import {
  fetchKnowledgeDocuments,
  uploadKnowledgeDocument,
  deleteKnowledgeDocument,
  fetchKnowledgeDocumentContent,
} from "@/lib/api";

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [previewDoc, setPreviewDoc] = useState<KnowledgeDocumentContent | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      const data = await fetchKnowledgeDocuments();
      setDocuments(data.items);
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

  const handleUpload = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("ファイルを選択してください");
      return;
    }

    const ext = file.name.toLowerCase();
    if (!ext.endsWith(".pdf") && !ext.endsWith(".pptx") && !ext.endsWith(".docx")) {
      setError("対応ファイル形式: PDF, PPTX, DOCX");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      await uploadKnowledgeDocument(
        file,
        description || undefined,
        category || undefined
      );
      setDescription("");
      setCategory("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("このドキュメントを削除しますか？")) return;
    try {
      await deleteKnowledgeDocument(id);
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handlePreview = async (id: number) => {
    setPreviewLoading(true);
    try {
      const content = await fetchKnowledgeDocumentContent(id);
      setPreviewDoc(content);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setPreviewLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const fileTypeIcon = (type: string) => {
    switch (type) {
      case "pdf": return "\u{1F4C4}";
      case "pptx": return "\u{1F4CA}";
      case "docx": return "\u{1F4DD}";
      default: return "\u{1F4CE}";
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-sm text-gray-500 mt-1">
          ナレッジベースにドキュメントをインポートして、記事生成に反映させます
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

      {/* Upload Form */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4">ドキュメントアップロード</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              ファイル (PDF, PPTX, DOCX)
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.pptx,.docx"
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                説明 (任意)
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="例: 会社概要資料"
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                カテゴリ (任意)
              </label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="例: 不動産, ブランド"
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
          </div>
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? "アップロード中..." : "アップロード"}
          </button>
        </div>
      </div>

      {/* Documents List */}
      <div className="bg-white rounded-xl shadow-sm border">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">
            登録済みドキュメント ({total})
          </h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading...</div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            ドキュメントがまだ登録されていません
          </div>
        ) : (
          <div className="divide-y">
            {documents.map((doc) => (
              <div key={doc.id} className="px-6 py-4 flex items-start gap-4">
                <span className="text-2xl">{fileTypeIcon(doc.file_type)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-gray-900 truncate">
                      {doc.filename}
                    </h3>
                    <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                      {doc.file_type.toUpperCase()}
                    </span>
                  </div>
                  {doc.description && (
                    <p className="text-sm text-gray-500 mt-0.5">
                      {doc.description}
                    </p>
                  )}
                  <div className="flex gap-4 mt-1 text-xs text-gray-400">
                    <span>{formatFileSize(doc.file_size)}</span>
                    <span>{doc.page_count} pages</span>
                    {doc.category && <span>Category: {doc.category}</span>}
                    <span>
                      {new Date(doc.created_at).toLocaleDateString("ja-JP")}
                    </span>
                  </div>
                  {doc.content_preview && (
                    <p className="text-xs text-gray-400 mt-1 truncate">
                      {doc.content_preview}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => handlePreview(doc.id)}
                    disabled={previewLoading}
                    className="px-3 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
                  >
                    View
                  </button>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="px-3 py-1 text-xs bg-gray-50 text-gray-500 rounded hover:bg-red-50 hover:text-red-600"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Document Content Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-bold truncate pr-4">
                {previewDoc.filename}
              </h3>
              <button
                onClick={() => setPreviewDoc(null)}
                className="px-3 py-1 text-sm bg-gray-100 text-gray-600 rounded hover:bg-gray-200 shrink-0"
              >
                Close
              </button>
            </div>
            <div className="overflow-y-auto px-6 py-4">
              {previewDoc.content_text ? (
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-800">
                  {previewDoc.content_text}
                </pre>
              ) : (
                <p className="text-gray-400 text-center py-8">
                  コンテンツがありません
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
