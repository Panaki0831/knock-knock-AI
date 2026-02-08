"use client";

import { useEffect, useState, useRef } from "react";
import type {
  KnowledgeDocument,
  KnowledgeDocumentContent,
  ImageAsset,
} from "@/lib/api";
import {
  fetchKnowledgeDocuments,
  uploadKnowledgeDocument,
  deleteKnowledgeDocument,
  fetchKnowledgeDocumentContent,
  fetchImages,
  uploadImage,
  deleteImage,
  imageFileUrl,
} from "@/lib/api";

type TabType = "documents" | "images";

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<TabType>("documents");

  // Document state
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [docTotal, setDocTotal] = useState(0);
  const [docLoading, setDocLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [previewDoc, setPreviewDoc] = useState<KnowledgeDocumentContent | null>(
    null
  );
  const [previewLoading, setPreviewLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Image state
  const [kbImages, setKbImages] = useState<ImageAsset[]>([]);
  const [imgTotal, setImgTotal] = useState(0);
  const [imgLoading, setImgLoading] = useState(true);
  const [imgUploading, setImgUploading] = useState(false);
  const [imgTags, setImgTags] = useState("");
  const [imgDescription, setImgDescription] = useState("");
  const [previewImage, setPreviewImage] = useState<ImageAsset | null>(null);
  const imgFileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = async () => {
    try {
      const data = await fetchKnowledgeDocuments();
      setDocuments(data.items);
      setDocTotal(data.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDocLoading(false);
    }
  };

  const loadImages = async () => {
    try {
      const data = await fetchImages({ is_knowledge_base: true });
      setKbImages(data.items);
      setImgTotal(data.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setImgLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
    loadImages();
  }, []);

  // Document handlers
  const handleDocUpload = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("ファイルを選択してください");
      return;
    }
    const ext = file.name.toLowerCase();
    if (
      !ext.endsWith(".pdf") &&
      !ext.endsWith(".pptx") &&
      !ext.endsWith(".docx")
    ) {
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
      await loadDocuments();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDocDelete = async (id: number) => {
    if (!confirm("このドキュメントを削除しますか？")) return;
    try {
      await deleteKnowledgeDocument(id);
      await loadDocuments();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDocPreview = async (id: number) => {
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

  // Image handlers
  const handleImgUpload = async () => {
    const file = imgFileInputRef.current?.files?.[0];
    if (!file) {
      setError("画像を選択してください");
      return;
    }
    setImgUploading(true);
    setError(null);
    try {
      await uploadImage(
        file,
        imgTags || undefined,
        imgDescription || undefined,
        true // is_knowledge_base
      );
      setImgTags("");
      setImgDescription("");
      if (imgFileInputRef.current) imgFileInputRef.current.value = "";
      await loadImages();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setImgUploading(false);
    }
  };

  const handleImgDelete = async (id: number) => {
    if (!confirm("この画像を削除しますか？")) return;
    try {
      await deleteImage(id);
      await loadImages();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const fileTypeIcon = (type: string) => {
    switch (type) {
      case "pdf":
        return "\u{1F4C4}";
      case "pptx":
        return "\u{1F4CA}";
      case "docx":
        return "\u{1F4DD}";
      default:
        return "\u{1F4CE}";
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-sm text-gray-500 mt-1">
          ナレッジベースにドキュメントや画像をインポートして、記事生成に反映させます
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

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => setActiveTab("documents")}
          className={`px-4 py-2 text-sm font-medium rounded-md ${
            activeTab === "documents"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Documents ({docTotal})
        </button>
        <button
          onClick={() => setActiveTab("images")}
          className={`px-4 py-2 text-sm font-medium rounded-md ${
            activeTab === "images"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Images ({imgTotal})
        </button>
      </div>

      {/* ── Documents Tab ──────────────────────────────────────────────── */}
      {activeTab === "documents" && (
        <>
          {/* Document Upload */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">
              ドキュメントアップロード
            </h2>
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
                onClick={handleDocUpload}
                disabled={uploading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {uploading ? "アップロード中..." : "アップロード"}
              </button>
            </div>
          </div>

          {/* Document List */}
          <div className="bg-white rounded-xl shadow-sm border">
            <div className="px-6 py-4 border-b">
              <h2 className="text-lg font-semibold">
                登録済みドキュメント ({docTotal})
              </h2>
            </div>
            {docLoading ? (
              <div className="p-8 text-center text-gray-400">Loading...</div>
            ) : documents.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                ドキュメントがまだ登録されていません
              </div>
            ) : (
              <div className="divide-y">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="px-6 py-4 flex items-start gap-4"
                  >
                    <span className="text-2xl">
                      {fileTypeIcon(doc.file_type)}
                    </span>
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
                        onClick={() => handleDocPreview(doc.id)}
                        disabled={previewLoading}
                        className="px-3 py-1 text-xs bg-blue-50 text-blue-700 rounded hover:bg-blue-100"
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleDocDelete(doc.id)}
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
        </>
      )}

      {/* ── Images Tab ─────────────────────────────────────────────────── */}
      {activeTab === "images" && (
        <>
          {/* Image Upload */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">画像アップロード</h2>
            <p className="text-xs text-gray-500 mb-4">
              Knock Knock
              AIに関連する画像をアップロードします。タグを設定すると、ライターが記事生成時に適切な画像を自動選定します。
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  画像ファイル (PNG, JPG, WEBP, GIF)
                </label>
                <input
                  ref={imgFileInputRef}
                  type="file"
                  accept=".png,.jpg,.jpeg,.webp,.gif"
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-100"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    タグ (カンマ区切り)
                  </label>
                  <input
                    type="text"
                    value={imgTags}
                    onChange={(e) => setImgTags(e.target.value)}
                    placeholder="例: 不動産, AI, バーチャルステージング"
                    className="w-full px-3 py-2 border rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    説明
                  </label>
                  <input
                    type="text"
                    value={imgDescription}
                    onChange={(e) => setImgDescription(e.target.value)}
                    placeholder="例: 会社ロゴ, オフィス外観"
                    className="w-full px-3 py-2 border rounded-lg text-sm"
                  />
                </div>
              </div>
              <button
                onClick={handleImgUpload}
                disabled={imgUploading}
                className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
              >
                {imgUploading ? "アップロード中..." : "画像をアップロード"}
              </button>
            </div>
          </div>

          {/* Image Grid */}
          <div className="bg-white rounded-xl shadow-sm border">
            <div className="px-6 py-4 border-b">
              <h2 className="text-lg font-semibold">
                登録済み画像 ({imgTotal})
              </h2>
            </div>
            {imgLoading ? (
              <div className="p-8 text-center text-gray-400">Loading...</div>
            ) : kbImages.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                画像がまだ登録されていません
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 p-6">
                {kbImages.map((img) => (
                  <div
                    key={img.id}
                    className="rounded-lg border overflow-hidden group"
                  >
                    <div
                      className="aspect-video bg-gray-100 cursor-pointer"
                      onClick={() => setPreviewImage(img)}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={imageFileUrl(img.id)}
                        alt={img.description || img.filename}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="p-2">
                      <p className="text-xs font-medium text-gray-700 truncate">
                        {img.description || img.filename}
                      </p>
                      {img.tags && img.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {img.tags.map((tag, i) => (
                            <span
                              key={i}
                              className="px-1.5 py-0.5 text-[10px] bg-green-50 text-green-700 rounded"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex justify-between items-center mt-1">
                        <span className="text-[10px] text-gray-400">
                          {formatFileSize(img.file_size)}
                        </span>
                        <button
                          onClick={() => handleImgDelete(img.id)}
                          className="text-[10px] text-gray-400 hover:text-red-600"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

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

      {/* Image Preview Modal */}
      {previewImage && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-bold truncate pr-4">
                {previewImage.description || previewImage.filename}
              </h3>
              <button
                onClick={() => setPreviewImage(null)}
                className="px-3 py-1 text-sm bg-gray-100 text-gray-600 rounded hover:bg-gray-200 shrink-0"
              >
                Close
              </button>
            </div>
            <div className="overflow-y-auto p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageFileUrl(previewImage.id)}
                alt={previewImage.description || previewImage.filename}
                className="w-full rounded-lg"
              />
              {previewImage.tags && previewImage.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {previewImage.tags.map((tag, i) => (
                    <span
                      key={i}
                      className="px-2 py-1 text-xs bg-green-50 text-green-700 rounded"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
