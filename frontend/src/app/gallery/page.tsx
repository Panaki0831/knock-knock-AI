"use client";

import { useEffect, useState, useRef } from "react";
import type { ImageAsset } from "@/lib/api";
import {
  fetchImages,
  uploadImage,
  deleteImage,
  imageFileUrl,
} from "@/lib/api";

type SourceFilter = "all" | "generated" | "uploaded";

export default function GalleryPage() {
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [tagFilter, setTagFilter] = useState("");
  const [tags, setTags] = useState("");
  const [description, setDescription] = useState("");
  const [previewImage, setPreviewImage] = useState<ImageAsset | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (sourceFilter !== "all") params.source = sourceFilter;
      if (tagFilter) params.tag = tagFilter;
      const data = await fetchImages(params);
      setImages(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [sourceFilter, tagFilter]);

  const handleUpload = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("ファイルを選択してください");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await uploadImage(file, tags || undefined, description || undefined, false);
      setTags("");
      setDescription("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("この画像を削除しますか？")) return;
    try {
      await deleteImage(id);
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const sourceBadge = (source: string) => {
    if (source === "generated")
      return (
        <span className="px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
          AI Generated
        </span>
      );
    if (source === "uploaded")
      return (
        <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
          Uploaded
        </span>
      );
    return (
      <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
        {source}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Image Gallery</h1>
        <p className="text-sm text-gray-500 mt-1">
          生成された画像やアップロードした画像を管理します。タグで検索・再利用が可能です。
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
        <h2 className="text-lg font-semibold mb-4">画像アップロード</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              画像ファイル (PNG, JPG, WEBP, GIF)
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.gif"
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                タグ (カンマ区切り)
              </label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
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
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="例: オフィスビルの外観写真"
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

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div className="flex gap-1">
          {(["all", "generated", "uploaded"] as SourceFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setSourceFilter(f)}
              className={`px-3 py-1.5 text-xs rounded-lg font-medium ${
                sourceFilter === f
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {f === "all" ? "All" : f === "generated" ? "AI Generated" : "Uploaded"}
            </button>
          ))}
        </div>
        <input
          type="text"
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          placeholder="タグで検索..."
          className="px-3 py-1.5 border rounded-lg text-sm w-64"
        />
        <span className="text-sm text-gray-400">{total} images</span>
      </div>

      {/* Image Grid */}
      {loading ? (
        <div className="p-8 text-center text-gray-400">Loading...</div>
      ) : images.length === 0 ? (
        <div className="p-8 text-center text-gray-400 bg-white rounded-xl shadow-sm border">
          画像がまだありません。アップロードするかパイプラインで記事を生成すると画像が追加されます。
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {images.map((img) => (
            <div
              key={img.id}
              className="bg-white rounded-xl shadow-sm border overflow-hidden group"
            >
              <div
                className="aspect-video bg-gray-100 cursor-pointer relative"
                onClick={() => setPreviewImage(img)}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imageFileUrl(img.id)}
                  alt={img.description || img.filename}
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-2 right-2">
                  {sourceBadge(img.source)}
                </div>
              </div>
              <div className="p-3">
                <p className="text-xs font-medium text-gray-700 truncate">
                  {img.description || img.filename}
                </p>
                {img.tags && img.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {img.tags.slice(0, 3).map((tag, i) => (
                      <span
                        key={i}
                        className="px-1.5 py-0.5 text-[10px] bg-gray-100 text-gray-500 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                    {img.tags.length > 3 && (
                      <span className="text-[10px] text-gray-400">
                        +{img.tags.length - 3}
                      </span>
                    )}
                  </div>
                )}
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[10px] text-gray-400">
                    {formatFileSize(img.file_size)}
                  </span>
                  <button
                    onClick={() => handleDelete(img.id)}
                    className="px-2 py-0.5 text-[10px] bg-gray-50 text-gray-400 rounded hover:bg-red-50 hover:text-red-600"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Image Preview Modal */}
      {previewImage && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <div>
                <h3 className="text-lg font-bold truncate">
                  {previewImage.description || previewImage.filename}
                </h3>
                <div className="flex gap-2 mt-1">
                  {sourceBadge(previewImage.source)}
                  {previewImage.is_knowledge_base && (
                    <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded">
                      Knowledge Base
                    </span>
                  )}
                </div>
              </div>
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
              <div className="mt-4 space-y-2">
                {previewImage.tags && previewImage.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {previewImage.tags.map((tag, i) => (
                      <span
                        key={i}
                        className="px-2 py-1 text-xs bg-blue-50 text-blue-700 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {previewImage.generation_prompt && (
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs font-medium text-gray-500 mb-1">
                      Generation Prompt:
                    </p>
                    <p className="text-xs text-gray-600">
                      {previewImage.generation_prompt}
                    </p>
                  </div>
                )}
                <div className="flex gap-4 text-xs text-gray-400">
                  {previewImage.width && previewImage.height && (
                    <span>
                      {previewImage.width}x{previewImage.height}
                    </span>
                  )}
                  <span>{formatFileSize(previewImage.file_size)}</span>
                  <span>
                    {new Date(previewImage.created_at).toLocaleDateString("ja-JP")}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
