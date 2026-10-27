import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, ImagePlus, LoaderCircle, Pencil, Rocket, Save, Trash2, Upload, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

// 素材库：蓝本 MediaAsset 的 Web 版。管理描述、用途、标签、生图提示词，
// 让视觉规划和创作页能拿到可解释的结构化素材，而不是只剩文件名。

interface MediaAsset {
  id: string;
  name: string;
  alt: string;
  visualDescription: string;
  usageHint: string;
  generationPrompt: string;
  tags: string[];
  descriptionSource: string;
  mime: string;
  source: string;
  origin: string;
  createdAt: string;
}

interface MediaForm {
  name: string;
  alt: string;
  visualDescription: string;
  usageHint: string;
  generationPrompt: string;
  tagsText: string;
}

const emptyForm: MediaForm = {
  name: "", alt: "", visualDescription: "", usageHint: "",
  generationPrompt: "", tagsText: "",
};

function toForm(asset: MediaAsset): MediaForm {
  return {
    name: asset.name,
    alt: asset.alt,
    visualDescription: asset.visualDescription,
    usageHint: asset.usageHint,
    generationPrompt: asset.generationPrompt,
    tagsText: (asset.tags ?? []).join(", "),
  };
}

export default function MediaPage() {
  const navigate = useNavigate();
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [search, setSearch] = useState("");
  const [origin, setOrigin] = useState<"" | "upload" | "generated">("");
  const [sort, setSort] = useState("created_desc");
  const [selected, setSelected] = useState<MediaAsset | null>(null);
  const [form, setForm] = useState<MediaForm>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ sort });
      if (search.trim()) params.set("search", search.trim());
      if (origin) params.set("origin", origin);
      const res = await api.get<{ assets: MediaAsset[] }>(`/media?${params.toString()}`);
      setAssets(res.data.assets ?? []);
    } catch {
      setError("无法加载素材库。");
    } finally {
      setLoading(false);
    }
  }, [search, origin, sort]);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        if (file.size > 8 * 1024 * 1024) {
          setError(`「${file.name}」超过 8MB，已跳过。`);
          continue;
        }
        const dataUrl = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result));
          reader.onerror = () => reject(reader.error);
          reader.readAsDataURL(file);
        });
        await api.post("/media", {
          name: file.name,
          mime: file.type,
          dataUrl,
          alt: file.name.replace(/\.[^.]+$/, ""),
          visualDescription: "请补充图片主体、构图与可用场景。",
          tags: ["上传"],
        });
      }
      await load();
    } catch {
      setError("上传失败。");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const generate = async () => {
    if (!prompt.trim()) {
      setError("请先填写图片描述。");
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      await api.post("/media/generate", { prompt: prompt.trim() });
      setPrompt("");
      await load();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "图片生成失败（需在管理端配置并录入数据库加密密钥）。");
    } finally {
      setGenerating(false);
    }
  };

  const saveDetails = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.patch<MediaAsset>(`/media/${selected.id}`, {
        name: form.name,
        alt: form.alt,
        visualDescription: form.visualDescription,
        usageHint: form.usageHint,
        generationPrompt: form.generationPrompt,
        tags: form.tagsText.split(/[,，]/).map((item) => item.trim()).filter(Boolean),
      });
      setSelected(res.data);
      setForm(toForm(res.data));
      await load();
    } catch {
      setError("保存素材信息失败。");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await api.delete(`/media/${id}`);
      if (selected?.id === id) {
        setSelected(null);
        setForm(emptyForm);
      }
      await load();
    } catch {
      setError("删除失败。");
    }
  };

  const removeSelected = async () => {
    if (!selectedIds.length || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await Promise.all(selectedIds.map((id) => api.delete(`/media/${id}`)));
      setSelectedIds([]);
      if (selected && selectedIds.includes(selected.id)) {
        setSelected(null);
        setForm(emptyForm);
      }
      await load();
    } catch {
      setError("批量删除失败。");
    } finally {
      setDeleting(false);
    }
  };

  const copyMarkdown = async (asset: MediaAsset) => {
    const markdown = `![${asset.alt || asset.name}](/api/media/${asset.id}/raw)`;
    await navigator.clipboard.writeText(markdown);
    setCopiedId(asset.id);
    setTimeout(() => setCopiedId(null), 1200);
  };

  const mediaMarkdown = (asset: MediaAsset) => `![${asset.alt || asset.name}](/api/media/${asset.id}/raw)`;

  const copySelectedMarkdown = async () => {
    const picked = assets.filter((asset) => selectedIds.includes(asset.id));
    if (picked.length === 0) return;
    await navigator.clipboard.writeText(picked.map(mediaMarkdown).join("\n\n"));
    setCopiedId("batch");
    setTimeout(() => setCopiedId(null), 1200);
  };

  const bringIntoCreation = () => {
    if (!selectedIds.length) return;
    navigate("/", { state: { selectedMediaIds: [...selectedIds] } });
  };

  const toggleSelected = (id: string) => {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  return (
    <section style={{ padding: "20px 24px", display: "grid", gap: 16, maxWidth: 1100 }}>
      <div>
        <p className="page-kicker">素材库</p>
        <h1>结构化图片素材</h1>
      </div>

      {error && (
        <div className="workflow-task__failure" role="alert">
          <p>{error}</p>
        </div>
      )}

      <div className="panel" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button className="button button--primary" disabled={uploading} onClick={() => fileRef.current?.click()} type="button">
            {uploading ? <LoaderCircle className="spin" size={15} /> : <Upload size={15} />}
            {uploading ? "上传中……" : "上传图片"}
          </button>
          <input
            accept="image/*"
            aria-label="选择图片文件"
            hidden
            multiple
            onChange={(event) => void upload(event.target.files)}
            ref={fileRef}
            type="file"
          />
          <span className="muted" style={{ fontSize: 12 }}>单张 ≤ 8MB · 图片类型</span>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="AI 生成：描述想要的图片……"
            style={{ flex: 3, minWidth: 220 }}
            value={prompt}
          />
          <button className="button button--quiet" disabled={generating} onClick={() => void generate()} type="button">
            {generating ? <LoaderCircle className="spin" size={15} /> : <ImagePlus size={15} />}
            {generating ? "生成中……" : "AI 生成"}
          </button>
        </div>
      </div>

      <div className="panel" style={{ display: "grid", gap: 10 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            aria-label="搜索素材"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索名称、描述、用途"
            style={{ flex: 2, minWidth: 180 }}
            value={search}
          />
          <select aria-label="素材来源" className="creation-select" onChange={(event) => setOrigin(event.target.value as "" | "upload" | "generated")} value={origin}>
            <option value="">全部来源</option>
            <option value="upload">上传</option>
            <option value="generated">AI 生成</option>
          </select>
          <select aria-label="排序" className="creation-select" onChange={(event) => setSort(event.target.value)} value={sort}>
            <option value="created_desc">最新优先</option>
            <option value="created_asc">最早优先</option>
            <option value="name_asc">名称 A-Z</option>
            <option value="name_desc">名称 Z-A</option>
          </select>
          <button
            className="button button--quiet"
            disabled={!selectedIds.length || deleting}
            onClick={() => void removeSelected()}
            type="button"
          >
            <Trash2 size={14} />
            {deleting ? "删除中" : `删除选中 ${selectedIds.length}`}
          </button>
          <button
            className="button button--quiet"
            disabled={!selectedIds.length}
            onClick={() => void copySelectedMarkdown()}
            type="button"
          >
            {copiedId === "batch" ? <Check size={14} /> : <Copy size={14} />}
            {copiedId === "batch" ? "已复制" : `复制选中 Markdown`}
          </button>
          <button
            className="button button--quiet"
            disabled={!selectedIds.length}
            onClick={bringIntoCreation}
            type="button"
          >
            <Rocket size={14} />
            带入创作页
          </button>
          <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>
            共 {assets.length} 个素材{selectedIds.length ? ` · 已选 ${selectedIds.length}` : ""}
          </span>
        </div>
      </div>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: selected ? "1fr 320px" : "1fr", minWidth: 0 }}>
        {loading ? (
          <p className="muted">加载中……</p>
        ) : assets.length === 0 ? (
          <p className="muted">没有匹配的素材。上传图片或调整筛选。</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 12, alignContent: "start" }}>
            {assets.map((asset) => (
              <figure
                className="panel"
                draggable
                key={asset.id}
                onDragStart={(event) => {
                  event.dataTransfer.setData("text/x-media-markdown", mediaMarkdown(asset));
                  event.dataTransfer.effectAllowed = "copy";
                }}
                style={{ display: "grid", gap: 8, margin: 0, padding: 10 }}
                title="拖入文章编辑器光标处插入"
              >
                <div style={{ position: "relative" }}>
                  <img
                    alt={asset.alt || asset.name}
                    src={asset.source}
                    style={{ width: "100%", height: 120, objectFit: "cover", borderRadius: 8 }}
                  />
                  <button
                    aria-label={`选择 ${asset.name}`}
                    className="icon-button"
                    onClick={() => toggleSelected(asset.id)}
                    style={{ position: "absolute", right: 6, top: 6 }}
                    type="button"
                  >
                    {selectedIds.includes(asset.id) ? <Check size={14} /> : " "}
                  </button>
                </div>
                <figcaption style={{ display: "grid", fontSize: 12, gap: 4 }}>
                  <strong style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{asset.name}</strong>
                  <span className="muted">{asset.origin === "generated" ? "AI 生成" : "上传"}</span>
                  <span className="muted" style={{ minHeight: 30 }}>
                    {asset.visualDescription || "缺少视觉描述"}
                  </span>
                  {(asset.tags ?? []).length > 0 && (
                    <span style={{ color: "var(--accent)", fontSize: 11 }}>{asset.tags.join(" · ")}</span>
                  )}
                </figcaption>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    className="button button--quiet"
                    onClick={() => { setSelected(asset); setForm(toForm(asset)); }}
                    type="button"
                  >
                    <Pencil size={13} />编辑
                  </button>
                  <button aria-label={`复制 ${asset.name} Markdown`} className="icon-button" onClick={() => void copyMarkdown(asset)} type="button">
                    {copiedId === asset.id ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                  <button aria-label={`删除 ${asset.name}`} className="icon-button" onClick={() => void remove(asset.id)} type="button">
                    <Trash2 size={14} />
                  </button>
                </div>
              </figure>
            ))}
          </div>
        )}

        {selected && (
          <aside aria-label="素材详情编辑" className="panel" style={{ display: "grid", gap: 10, height: "fit-content" }}>
            <div style={{ alignItems: "center", display: "flex", justifyContent: "space-between" }}>
              <h2 style={{ fontSize: 16, margin: 0 }}>素材详情</h2>
              <button aria-label="关闭素材详情" className="icon-button" onClick={() => setSelected(null)} type="button">
                <X size={15} />
              </button>
            </div>
            <img alt="" src={selected.source} style={{ borderRadius: 8, maxHeight: 180, objectFit: "cover", width: "100%" }} />
            <label className="field"><span>名称</span>
              <input onChange={(event) => setForm({ ...form, name: event.target.value })} value={form.name} />
            </label>
            <label className="field"><span>短描述 / alt</span>
              <input onChange={(event) => setForm({ ...form, alt: event.target.value })} value={form.alt} />
            </label>
            <label className="field"><span>视觉描述</span>
              <textarea
                onChange={(event) => setForm({ ...form, visualDescription: event.target.value })}
                placeholder="主体、构图、色彩、风格，用于素材匹配"
                rows={4}
                value={form.visualDescription}
              />
            </label>
            <label className="field"><span>使用场景</span>
              <input
                onChange={(event) => setForm({ ...form, usageHint: event.target.value })}
                placeholder="例如：产品架构节 / 对比场景"
                value={form.usageHint}
              />
            </label>
            <label className="field"><span>生图提示词</span>
              <textarea
                onChange={(event) => setForm({ ...form, generationPrompt: event.target.value })}
                rows={4}
                value={form.generationPrompt}
              />
            </label>
            <label className="field"><span>标签（逗号分隔）</span>
              <input
                onChange={(event) => setForm({ ...form, tagsText: event.target.value })}
                value={form.tagsText}
              />
            </label>
            <small className="muted">描述来源：{selected.descriptionSource || "manual"}</small>
            <button className="button button--primary" disabled={saving} onClick={() => void saveDetails()} type="button">
              {saving ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}
              {saving ? "保存中" : "保存素材"}
            </button>
          </aside>
        )}
      </div>
    </section>
  );
}
