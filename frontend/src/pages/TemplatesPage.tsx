import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { Copy, LoaderCircle, Save, Trash2, Wand2 } from "lucide-react";
import { api } from "../api/client";
import { useNavigate } from "react-router-dom";

// 模板库：蓝本 MarkdownTemplate 的结构画像 Web 版。
// 不只保存骨架，也保存文风、结构、排版和固定块，供后续创作 Agent 消费。

interface TemplateProfile {
  tone?: string;
  readerRelationship?: string;
  forbiddenPatterns?: string[] | string;
  preferredEvidence?: string;
  sectionOrder?: string[] | string;
  sectionPurposes?: string[] | string;
  transitionStyle?: string;
  ctaPosition?: string;
  headingLevelRule?: string;
  paragraphLength?: string;
  listUsage?: string;
  emphasisStyle?: string;
}

interface MarkdownTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  markdown: string;
  styleProfile: TemplateProfile | null;
  structureProfile: TemplateProfile | null;
  layoutProfile: TemplateProfile | null;
  fixedBlocks: Array<{ name?: string; content?: string; position?: string }> | null;
  variables: string[] | null;
  usageInstructions: string;
  isBuiltIn: boolean;
  mode: string;
  referenceMarkdown?: string | null;
  sourceFingerprint?: string | null;
}

interface TemplateForm {
  name: string;
  description: string;
  category: string;
  markdown: string;
  usageInstructions: string;
  styleProfile: string;
  structureProfile: string;
  layoutProfile: string;
  fixedBlocks: string;
  variables: string;
}

function jsonText(value: unknown) {
  return value == null ? "{}" : JSON.stringify(value, null, 2);
}

function toForm(template: MarkdownTemplate): TemplateForm {
  return {
    name: template.name,
    description: template.description,
    category: template.category,
    markdown: template.markdown,
    usageInstructions: template.usageInstructions,
    styleProfile: jsonText(template.styleProfile),
    structureProfile: jsonText(template.structureProfile),
    layoutProfile: jsonText(template.layoutProfile),
    fixedBlocks: jsonText(template.fixedBlocks ?? []),
    variables: (template.variables ?? []).join(", "),
  };
}

function parseJson<T>(value: string, label: string): T {
  try {
    return JSON.parse(value || "null") as T;
  } catch {
    throw new Error(`${label} 不是有效 JSON。`);
  }
}

export default function TemplatesPage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<MarkdownTemplate[]>([]);
  const [selected, setSelected] = useState<MarkdownTemplate | null>(null);
  const [form, setForm] = useState<TemplateForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [extractSource, setExtractSource] = useState("");
  const [extracting, setExtracting] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get<{ templates: MarkdownTemplate[] }>("/templates");
      setTemplates(res.data.templates);
      setSelected((current) =>
        current && res.data.templates.some((template) => template.id === current.id)
          ? res.data.templates.find((template) => template.id === current.id) ?? null
          : res.data.templates[0] ?? null,
      );
    } catch {
      setError("无法加载模板列表。");
    }
  }, []);

  useEffect(() => {
    if (selected) setForm(toForm(selected));
    setError(null);
  }, [selected]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async () => {
    if (!name.trim() || !markdown.trim()) {
      setError("模板名称与正文不能为空。");
      return;
    }
    setError(null);
    try {
      const res = await api.post<MarkdownTemplate>("/templates", {
        name, description, category: "自定义", markdown,
      });
      setName("");
      setDescription("");
      setMarkdown("");
      await load();
      setSelected(res.data);
    } catch {
      setError("创建模板失败。");
    }
  };

  const remove = async (id: string) => {
    try {
      await api.delete(`/templates/${id}`);
      await load();
    } catch {
      setError("删除失败（内置模板不可删除）。");
    }
  };

  const extract = async () => {
    if (!extractSource.trim()) {
      setError("请先粘贴参考文章。");
      return;
    }
    setExtracting(true);
    setError(null);
    try {
      const res = await api.post<MarkdownTemplate>("/templates/extract", {
        markdown: extractSource,
      });
      setExtractSource("");
      await load();
      setSelected(res.data);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(
        typeof detail === "string" && detail
          ? detail
          : "模板提取失败，请稍后重试或检查模型配置。",
      );
    } finally {
      setExtracting(false);
    }
  };

  const duplicate = async () => {
    if (!selected) return;
    setError(null);
    try {
      const res = await api.post<MarkdownTemplate>("/templates", {
        name: `${selected.name} 副本`,
        description: selected.description,
        category: "自定义",
        markdown: selected.markdown,
      });
      await load();
      setSelected(res.data);
    } catch {
      setError("复制模板失败。");
    }
  };

  const save = async () => {
    if (!selected || !form) return;
    if (selected.isBuiltIn) {
      setError("内置模板不可修改，可复制后另存为自定义模板。");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const styleProfile = parseJson<Record<string, unknown>>(form.styleProfile, "文风画像");
      const structureProfile = parseJson<Record<string, unknown>>(form.structureProfile, "结构画像");
      const layoutProfile = parseJson<Record<string, unknown>>(form.layoutProfile, "排版画像");
      const fixedBlocks = parseJson<Array<Record<string, unknown>>>(form.fixedBlocks, "固定块");
      const res = await api.patch<MarkdownTemplate>(`/templates/${selected.id}`, {
        name: form.name,
        description: form.description,
        category: form.category,
        markdown: form.markdown,
        usageInstructions: form.usageInstructions,
        styleProfile,
        structureProfile,
        layoutProfile,
        fixedBlocks,
        variables: form.variables.split(/[,，]/).map((item) => item.trim()).filter(Boolean),
      });
      await load();
      setSelected(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存模板失败。");
    } finally {
      setSaving(false);
    }
  };

  const update = (patch: Partial<TemplateForm>) => {
    setForm((current) => (current ? { ...current, ...patch } : current));
  };

  return (
    <section className="articles-layout" style={{ "--article-browser-width": "248px" } as CSSProperties}>
      <aside aria-label="模板列表" className="article-browser">
        <div className="article-browser__head">
          <div>
            <span className="page-kicker">模板库</span>
            <strong>模板</strong>
          </div>
        </div>
        <div className="article-list">
          {templates.map((template) => (
            <button
              aria-current={selected?.id === template.id ? "true" : undefined}
              className={`article-list-item${selected?.id === template.id ? " is-active" : ""}`}
              key={template.id}
              onClick={() => setSelected(template)}
              type="button"
            >
              <span className="article-status article-status--draft">
                {template.isBuiltIn ? "内置" : template.mode === "reference" ? "提取" : "自定义"}
              </span>
              <strong>{template.name}</strong>
              <span className="article-list-item__meta"><span>{template.category}</span></span>
            </button>
          ))}
        </div>
      </aside>
      <div aria-hidden="true" className="article-browser__resizer" role="separator" tabIndex={-1} />
      <div className="article-editor">
        <header className="article-editor__head">
          <div className="article-editor__title">
            {selected ? (
              <>
                <span className="page-kicker">{selected.category}</span>
                <strong>{selected.name}</strong>
              </>
            ) : <strong>选择模板</strong>}
          </div>
          <div className="article-editor__actions">
            {selected && (
              <>
                <button
                  className="button button--quiet"
                  disabled={selected.isBuiltIn}
                  onClick={() => void save()}
                  type="button"
                >
                  {saving ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}
                  {saving ? "保存中" : "保存画像"}
                </button>
                <button
                  className="button button--quiet"
                  onClick={() => void duplicate()}
                  type="button"
                >
                  <Copy size={15} />
                  复制另存
                </button>
                <button
                  className="button button--primary"
                  onClick={() => navigate(`/articles?template=${selected.id}`)}
                  type="button"
                >
                  用于创作
                </button>
                {!selected.isBuiltIn && (
                  <button
                    aria-label={`删除 ${selected.name}`}
                    className="icon-button"
                    onClick={() => void remove(selected.id)}
                    type="button"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </>
            )}
          </div>
        </header>


        <div className="article-editor__scroll">
        {error && (
          <div className="workflow-task__failure" role="alert"><p>{error}</p></div>
        )}
        {selected && form && (
          <div style={{ display: "grid", gap: 10, maxWidth: 940 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <label className="field"><span>名称</span>
                <input disabled={selected.isBuiltIn} onChange={(event) => update({ name: event.target.value })} value={form.name} />
              </label>
              <label className="field"><span>分类</span>
                <input disabled={selected.isBuiltIn} onChange={(event) => update({ category: event.target.value })} value={form.category} />
              </label>
            </div>
            <label className="field"><span>描述</span>
              <input disabled={selected.isBuiltIn} onChange={(event) => update({ description: event.target.value })} value={form.description} />
            </label>
            <label className="field"><span>模板骨架</span>
              <textarea
                disabled={selected.isBuiltIn}
                onChange={(event) => update({ markdown: event.target.value })}
                rows={10}
                value={form.markdown}
              />
            </label>
            <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
              <label className="field"><span>文风画像 styleProfile</span>
                <textarea disabled={selected.isBuiltIn} onChange={(event) => update({ styleProfile: event.target.value })} rows={6} value={form.styleProfile} />
              </label>
              <label className="field"><span>结构画像 structureProfile</span>
                <textarea disabled={selected.isBuiltIn} onChange={(event) => update({ structureProfile: event.target.value })} rows={6} value={form.structureProfile} />
              </label>
              <label className="field"><span>排版画像 layoutProfile</span>
                <textarea disabled={selected.isBuiltIn} onChange={(event) => update({ layoutProfile: event.target.value })} rows={6} value={form.layoutProfile} />
              </label>
              <label className="field"><span>固定块 fixedBlocks</span>
                <textarea disabled={selected.isBuiltIn} onChange={(event) => update({ fixedBlocks: event.target.value })} rows={6} value={form.fixedBlocks} />
              </label>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <label className="field"><span>变量</span>
                <input disabled={selected.isBuiltIn} onChange={(event) => update({ variables: event.target.value })} value={form.variables} />
              </label>
              <label className="field"><span>使用说明</span>
                <input disabled={selected.isBuiltIn} onChange={(event) => update({ usageInstructions: event.target.value })} value={form.usageInstructions} />
              </label>
            </div>
          </div>
        )}

        <div style={{ display: "grid", gap: 12, maxWidth: 940, marginTop: 20 }}>
          <div className="panel" style={{ display: "grid", gap: 10 }}>
            <h2 style={{ margin: 0 }}>新建模板</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <input onChange={(event) => setName(event.target.value)} placeholder="模板名称" value={name} />
              <input onChange={(event) => setDescription(event.target.value)} placeholder="一句话描述" value={description} />
            </div>
            <textarea
              onChange={(event) => setMarkdown(event.target.value)}
              placeholder="Markdown 模板骨架"
              rows={6}
              value={markdown}
            />
            <button className="button button--primary" onClick={() => void create()} type="button">创建模板</button>
          </div>

          <div className="panel" style={{ display: "grid", gap: 10 }}>
            <h2 style={{ margin: 0 }}>从参考文章提取</h2>
            <p className="muted" style={{ fontSize: 12 }}>
              只提取结构与表达方式；事实内容会被替换为变量。提取会同时生成文风、结构、排版画像。
            </p>
            <textarea
              onChange={(event) => setExtractSource(event.target.value)}
              placeholder="粘贴参考文章……"
              rows={7}
              value={extractSource}
            />
            <button className="button button--quiet" disabled={extracting} onClick={() => void extract()} type="button">
              {extracting ? <LoaderCircle className="spin" size={15} /> : <Wand2 size={15} />}
              {extracting ? "提取中……" : "提取模板"}
            </button>
          </div>
        </div>
        </div>
      </div>
    </section>
  );
}
