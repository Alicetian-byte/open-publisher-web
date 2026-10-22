import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Eye, FileText, FileUp, GripVertical, History, ImagePlus, LoaderCircle, Pencil, Plus, Save, Search, Sparkles, Undo2, Upload, XCircle } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { bridge } from "../lib/bridge";
import {
  AssistantDrawer,
  PublishDialog,
  RewriteDialog,
  RevisionHistoryDrawer,
} from "../components/article/ArticleTools";
import { MarkdownWorkbench, type ImageInsertion, type MarkdownSelection, type PreviewPlatform } from "../components/article/MarkdownWorkbench";

// 文章库：蓝本 ArticlesPage 的 Web 版核心闭环（团队自有代码）。
// 本轮实现：列表 + 创作 run（SSE）+ 查看/编辑保存新版本；
// MarkdownWorkbench / PublishDialog / Assistant 完整迁移见路线图。

interface ArticleState {
  articleId: string;
  title: string;
  currentRevisionId: string | null;
  contentHash: string | null;
  markdown: string;
  updatedAt: string | null;
}

interface RunEventItem {
  sequence: number;
  type: string;
  payload: Record<string, unknown>;
}

interface VisualPlanPlacement {
  id: string;
  anchorHeading: string | null;
  anchorExcerpt: string | null;
  alt: string;
  source: "existing_asset" | "generate";
  assetId: string | null;
  candidates: Array<{ assetId: string; score: number; description: string }>;
  selectionReason: string;
  generationPrompt: string;
}

interface VisualPlanSummary {
  targetCount: number;
  placements: VisualPlanPlacement[];
  sourceRevisionId: string | null;
  sourceContentHash: string | null;
}

interface VisualApplyResult {
  article: ArticleState;
  insertedCount: number;
  skipped: Array<{ id: string; reason: string }>;
}


// 创作事件（RunJournal）的可读文案与状态图标
const JOURNAL_LABELS: Record<string, string> = {
  "run.started": "任务开始",
  "run.completed": "任务完成",
  "run.failed": "任务失败",
  "run.stopped": "任务已停止",
  "agent.message_delta": "写作 Agent 正在撰写正文……",
  "article.checkpointed": "正文初稿已生成（不可变版本）",
  "revision.committed": "文章已保存新版本",
  "rewrite.candidate_ready": "改写候选已生成",
};

function journalEventState(type: string): "running" | "complete" | "failed" {
  if (type === "run.failed") return "failed";
  if (type === "run.completed" || type === "revision.committed") return "complete";
  return "running";
}

function journalEventMessage(type: string, payload: Record<string, unknown>): string {
  const message = payload.message ?? payload.stage ?? payload.reason;
  return JOURNAL_LABELS[type] ?? (typeof message === "string" ? message : type);
}

const LENGTH_OPTIONS = [
  { id: "short", label: "短篇（1500-2000 字）" },
  { id: "medium", label: "中篇（3000-4000 字）" },
  { id: "long", label: "长篇（5500-7000 字）" },
  { id: "custom", label: "自定义篇幅" },
];

export default function ArticlesPage() {
  const navigate = useNavigate();
  const [articles, setArticles] = useState<ArticleState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<ArticleState | null>(null);
  const [creating, setCreating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [tone, setTone] = useState("");
  const [lengthPreset, setLengthPreset] = useState("medium");
  const [customLength, setCustomLength] = useState("");
  const [humanize, setHumanize] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<RunEventItem[]>([]);
  const [running, setRunning] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [viewMode, setViewMode] = useState<"edit" | "split" | "preview">("edit");
  const [previewPlatform, setPreviewPlatform] = useState<PreviewPlatform>("general");
  const [imagePickerOpen, setImagePickerOpen] = useState(false);
  const [rewriteOpen, setRewriteOpen] = useState(false);
  const [visualBusy, setVisualBusy] = useState(false);
  const [visualPlan, setVisualPlan] = useState<VisualPlanSummary | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [pendingInsertion, setPendingInsertion] = useState<string | null>(null);
  const [rewriteSelection, setRewriteSelection] = useState<MarkdownSelection | null>(null);
  const [lastAiSnapshot, setLastAiSnapshot] = useState<{
    label: string;
    markdown: string;
    currentRevisionId: string | null;
    contentHash: string | null;
  } | null>(null);
  const [excludedPlacementIds, setExcludedPlacementIds] = useState<string[]>([]);
  const [referenceNote, setReferenceNote] = useState<string | null>(null);
  const [referenceNames, setReferenceNames] = useState<string[]>([]);
  const [referenceDrag, setReferenceDrag] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const esRef = useRef<EventSource | null>(null);
  const userEditedRef = useRef(false);

  // 模板参数：从模板库跳转过来时，把模板骨架注入创作要求
  useEffect(() => {
    const templateId = searchParams.get("template");
    if (!templateId) return;
    api
      .get<{ templates: Array<{ id: string; name: string; markdown: string; usageInstructions: string }> }>("/templates")
      .then((res) => {
        const t = res.data.templates.find((item) => item.id === templateId);
        if (t) {
          setPrompt((current) =>
            current
              ? current
              : `请按「${t.name}」模板的结构创作：\n\n${t.markdown}\n\n${t.usageInstructions}`,
          );
          setCreating(true);
          setSelected(null);
        }
      })
      .catch(() => undefined);
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  const loadArticles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ articles: ArticleState[] }>("/articles");
      setArticles(res.data.articles);
    } catch {
      setError("无法加载文章列表，请确认后端服务已启动。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadArticles();
  }, [loadArticles]);

  // ?new=1：顶栏「新文章」入口直接打开新建创作面板
  useEffect(() => {
    if (searchParams.get("new") === "1") {
      setSelected(null);
      setCreating(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // ?open=<articleId>：深链直接选中文章（发布计划/助手等入口的回跳能力）
  useEffect(() => {
    const openId = searchParams.get("open");
    if (!openId) return;
    api
      .get<ArticleState>(`/articles/${openId}`)
      .then((res) => {
        setSelected(res.data);
        setCreating(false);
        setRunId(null);
      })
      .catch(() => undefined);
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    setDraft(selected?.markdown ?? "");
    userEditedRef.current = false;
  }, [selected]);

  const filtered = articles.filter(
    (a) =>
      !query.trim() ||
      a.title.toLowerCase().includes(query.trim().toLowerCase()),
  );


  // 蓝本 onImageFileDrop 的 Web 等价：读为 data URL 上传素材库，返回站内引用
  const uploadImageFile = async (file: File): Promise<ImageInsertion> => {
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("读取图片文件失败。"));
      reader.readAsDataURL(file);
    });
    const res = await api.post<{ id: string; name: string }>("/media", {
      name: file.name,
      source: dataUrl,
      alt: file.name.replace(/\.[^.]+$/, ""),
    });
    return { alt: file.name.replace(/\.[^.]+$/, ""), src: `/api/media/${res.data.id}/raw` };
  };

  // 蓝本 CreatePage 资料文件夹导入的 Web 等价：选文本资料（.md/.txt），并入创作要求
  const importReferenceFiles = async (files: FileList | null) => {
    if (!files || !files.length) return;
    const texts = await Promise.all(
      Array.from(files).map(async (file) => {
        const text = await file.text();
        return `## 参考资料：${file.name}\n\n${text.trim()}`;
      }),
    );
    const names = Array.from(files).map((file) => file.name);
    setPrompt((current) =>
      `${current ? `${current}\n\n` : ""}${texts.join("\n\n")}`.slice(0, 60000),
    );
    setReferenceNames(names);
    setReferenceNote(`已并入 ${files.length} 个资料文件（事实只来自这些资料）。`);
  };

  const startRun = async () => {
    if (!prompt.trim()) {
      setError("请先填写创作要求。");
      return;
    }
    setError(null);
    setEvents([]);
    setRunning(true);
    setCreating(false);
    const articleId = `article-${Date.now()}`;
    try {
      const run = await bridge.createArticleRun({
        articleId,
        prompt: prompt.trim(),
        tone: tone || null,
        lengthPreset,
        customLength: lengthPreset === "custom" ? customLength : null,
        humanize,
      });
      setRunId(run.id);
      // 蓝本交互：发起后立即迁移到文章工作区，由 run 事件继续驱动编辑器。
      try {
        const article = await bridge.getArticle(articleId);
        setSelected(article);
      } catch {
        setSelected({
          articleId,
          title: prompt.slice(0, 80),
          currentRevisionId: null,
          contentHash: null,
          markdown: "",
          updatedAt: null,
        });
      }
      setCreating(false);
      esRef.current = bridge.openRunStream(run.id, {
        onEvent: (event) => {
          setEvents((prev) => [...prev, event as RunEventItem]);
          if (
            event.type === "agent.message_delta"
            && (event.payload as { stage?: string; delta?: string } | undefined)?.stage === "content"
          ) {
            const delta = (event.payload as { delta?: string }).delta ?? "";
            if (delta && !userEditedRef.current) {
              setDraft((current) => current + delta);
            }
          }
          if (event.type === "run.completed") {
            setRunning(false);
            void loadArticles();
            void bridge.getArticle(articleId)
              .then((article) => setSelected(article))
              .catch(() => undefined);
          }
          if (event.type === "run.failed") {
            setRunning(false);
            setError(`创作失败：${String((event.payload as { message?: string } | undefined)?.message ?? "未知错误")}`);
          }
        },
        onEnd: () => {
          setRunning(false);
          void loadArticles();
        },
      });
    } catch {
      setError("启动创作运行失败，请确认后端服务已启动。");
      setRunning(false);
    }
  };

  // 智能配图：蓝本 visual-plan → 用户确认 → visual-apply 的三段式 Web 版
  const startVisualPlan = async () => {
    if (!selected || visualBusy) return;
    setExcludedPlacementIds([]);
    setVisualBusy(true);
    setError(null);
    try {
      const res = await api.post<VisualPlanSummary>(
        `/articles/${selected.articleId}/visual-plan`,
        { targetCount: 2, assetIds: [] },
      );
      if (res.data.placements.length === 0) {
        setError("视觉规划认为本文不需要配图。");
      } else {
        setVisualPlan(res.data);
      }
    } catch {
      setError("配图规划失败，请稍后重试。");
    } finally {
      setVisualBusy(false);
    }
  };

  const confirmVisualApply = async () => {
    if (!selected || !visualPlan || visualBusy) return;
    const placements = visualPlan.placements.filter(
      (placement) => !excludedPlacementIds.includes(placement.id),
    );
    if (!placements.length) {
      setError("请至少保留一张配图，或关闭方案。");
      return;
    }
    setLastAiSnapshot({
      label: "智能配图",
      markdown: selected.markdown,
      currentRevisionId: selected.currentRevisionId,
      contentHash: selected.contentHash,
    });
    setVisualBusy(true);
    setError(null);
    try {
      const res = await api.post<VisualApplyResult>(
        `/articles/${selected.articleId}/visual-apply`,
        {
          baseRevisionId: selected.currentRevisionId,
          baseContentHash: selected.contentHash,
          placements,
        },
      );
      setSelected(res.data.article);
      setDraft(res.data.article.markdown);
      setVisualPlan(null);
      setExcludedPlacementIds([]);
      void loadArticles();
    } catch {
      setError("配图应用失败：文章可能已被修改，请刷新后重试。");
    } finally {
      setVisualBusy(false);
    }
  };

  const saveVersion = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      await api.post("/articles", {
        articleId: selected.articleId,
        baseRevisionId: selected.currentRevisionId,
        baseContentHash: selected.contentHash,
        title: selected.title,
        markdown: draft,
        reason: "web 编辑",
      });
      await loadArticles();
      const fresh = await api.get<ArticleState>(`/articles/${selected.articleId}`);
      setSelected(fresh.data);
    } catch {
      setError("保存失败：文章可能已被其他操作修改，请刷新后重试。");
    } finally {
      setSaving(false);
    }
  };

  const runFailed = events.some((event) => event.type === "run.failed");

  const undoLastAiChange = async () => {
    if (!selected || !lastAiSnapshot) return;
    if (
      lastAiSnapshot.currentRevisionId === selected.currentRevisionId
      && lastAiSnapshot.contentHash === selected.contentHash
    ) {
      // 本地 AI 改写还未提交新版本，直接回滚编辑器草稿即可。
      setDraft(lastAiSnapshot.markdown);
      setLastAiSnapshot(null);
      return;
    }
    try {
      await api.post("/articles", {
        articleId: selected.articleId,
        baseRevisionId: selected.currentRevisionId,
        baseContentHash: selected.contentHash,
        title: selected.title,
        markdown: lastAiSnapshot.markdown,
        reason: `undo ${lastAiSnapshot.label}`,
      });
      await loadArticles();
      const fresh = await api.get<ArticleState>(`/articles/${selected.articleId}`);
      setSelected(fresh.data);
      setLastAiSnapshot(null);
    } catch {
      setError("撤销失败：文章可能已被修改，请刷新后重试。");
    }
  };

  const dirty = selected !== null && draft !== selected.markdown;
  const layoutStyle = { "--article-browser-width": "248px" } as CSSProperties;

  return (
    <section className="articles-layout" style={layoutStyle}>
      <aside aria-label="文章列表" className="article-browser">
        <div className="article-browser__head">
          <div>
            <span className="page-kicker">文章库</span>
            <strong>文章</strong>
          </div>
          <button
            aria-label="新建文章"
            className="icon-button"
            onClick={() => {
              setCreating(true);
              setError(null);
              setSelected(null);
            }}
            title="新建文章"
            type="button"
          >
            <Plus size={16} />
          </button>
        </div>
        <label className="article-search">
          <Search aria-hidden="true" size={14} />
          <span className="visually-hidden">搜索文章</span>
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索文章"
            value={query}
          />
        </label>
        <div className="article-list">
          {filtered.map((article) => (
            <button
              aria-current={selected?.articleId === article.articleId ? "true" : undefined}
              className={`article-list-item${selected?.articleId === article.articleId ? " is-active" : ""}`}
              key={article.articleId}
              onClick={() => {
                setSelected(article);
                setCreating(false);
                setRunId(null);
                setEvents([]);
              }}
              type="button"
            >
              <span className="article-status article-status--draft">文章</span>
              <strong>{article.title}</strong>
              <span className="article-list-item__meta">
                <span>
                  {article.updatedAt
                    ? new Date(article.updatedAt).toLocaleDateString()
                    : ""}
                </span>
              </span>
            </button>
          ))}
          {filtered.length === 0 && !loading && (
            <p className="article-list__empty">还没有文章，点右上角 + 新建</p>
          )}
        </div>
      </aside>

      <div
        aria-hidden="true"
        className="article-browser__resizer"
        role="separator"
        tabIndex={-1}
      >
        <GripVertical size={14} />
      </div>

      <div className="article-editor">
        <header className="article-editor__head">
          <div className="article-editor__title">
            {creating ? (
              <>
                <span className="page-kicker">新建文章</span>
                <strong>创作要求</strong>
              </>
            ) : selected ? (
              <>
                <span className="article-status article-status--draft">文章</span>
                <strong>{selected.title}</strong>
              </>
            ) : (
              <strong>选择一篇文章</strong>
            )}
          </div>
          <div className="article-editor__actions">
            {selected && !creating && (
              <>
                <button
                  className="button button--quiet"
                  onClick={() => setAssistantOpen((v) => !v)}
                  type="button"
                >
                  <Sparkles size={15} />
                  助手
                </button>
                <button
                  className="button button--quiet"
                  onClick={() => setRewriteOpen(true)}
                  type="button"
                >
                  <Pencil size={15} />
                  AI 改写
                </button>
                <button
                  className="button button--quiet"
                  disabled={!selected.currentRevisionId}
                  onClick={() => setPublishOpen(true)}
                  type="button"
                >
                  <Upload size={15} />
                  发布
                </button>
                <button
                  className="button button--quiet"
                  onClick={() =>
                    setViewMode((m) => (m === "edit" ? "split" : m === "split" ? "preview" : "edit"))
                  }
                  type="button"
                >
                  {viewMode === "edit" ? <Eye size={15} /> : <Pencil size={15} />}
                  {viewMode === "edit" ? "分栏" : viewMode === "split" ? "预览" : "编辑"}
                </button>
                <button
                  className="button button--quiet"
                  onClick={() => setImagePickerOpen(true)}
                  type="button"
                >
                  <ImagePlus size={15} />
                  插图
                </button>
                <button
                  className="button button--quiet"
                  disabled={visualBusy}
                  onClick={() => void startVisualPlan()}
                  type="button"
                >
                  <Sparkles size={15} />
                  {visualBusy ? "配图中" : "智能配图"}
                </button>
                <button
                  className="button button--quiet"
                  disabled={!lastAiSnapshot}
                  onClick={() => void undoLastAiChange()}
                  type="button"
                >
                  <Undo2 size={15} />
                  撤销 AI 修改
                </button>
                <button
                  className="button button--quiet"
                  onClick={() => setHistoryOpen(true)}
                  type="button"
                >
                  <History size={15} />
                  历史
                </button>
                <button
                  aria-label="保存新版本"
                  className="button button--primary"
                  disabled={saving || !dirty}
                  onClick={() => void saveVersion()}
                  type="button"
                >
                  {saving ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />}
                  {saving ? "保存中" : dirty ? "保存新版本" : "已保存"}
                </button>
              </>
            )}
          </div>
        </header>

        <div className="article-editor__body" style={{ overflowY: "auto", padding: "20px 24px" }}>
          {error && (
            <div className="workflow-task__failure" role="alert" style={{ marginBottom: 14 }}>
              <p>{error}</p>
            </div>
          )}
          {creating && (
            <div style={{ display: "grid", gap: 14, maxWidth: 720 }}>
              <div className="field">
                <div className="field__head">
                  <label htmlFor="a-prompt">创作要求</label>
                  <span className="field-tag field-tag--required">必填</span>
                </div>
                <small>写什么、给谁看、重点是什么。事实只来自这里，AI 不会编造。</small>
                <textarea
                  id="a-prompt"
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="例如：为我们的开源项目写一篇产品推广文章，目标读者是独立开发者……"
                  rows={6}
                  value={prompt}
                />
              </div>
              <div className="field">
                <div className="field__head">
                  <label htmlFor="a-materials">资料文件（可选）</label>
                </div>
                <small>
                  蓝本资料文件夹导入的 Web 等价：选择 .md / .txt 资料，
                  内容会并入创作要求，AI 只引用这些资料中的事实。
                </small>
                <div
                  className={`materials-dropzone${referenceDrag ? " materials-dropzone--drag" : ""}`}
                  onDragLeave={() => setReferenceDrag(false)}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setReferenceDrag(true);
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    setReferenceDrag(false);
                    void importReferenceFiles(e.dataTransfer.files);
                  }}
                >
                  <FileUp aria-hidden size={20} strokeWidth={1.8} />
                  <div className="materials-dropzone__text">
                    <strong>点击选择或拖入 .md / .txt 资料</strong>
                    <span>支持多选，内容会并入上方创作要求</span>
                  </div>
                  <input
                    accept=".md,.markdown,.txt,text/markdown,text/plain"
                    id="a-materials"
                    multiple
                    onChange={(e) => {
                      void importReferenceFiles(e.target.files);
                      e.target.value = "";
                    }}
                    tabIndex={-1}
                    type="file"
                  />
                </div>
                {referenceNames.length > 0 && (
                  <ul className="materials-dropzone__files">
                    {referenceNames.map((name) => (
                      <li key={name}>
                        <FileText aria-hidden size={12} />
                        {name}
                      </li>
                    ))}
                  </ul>
                )}
                {referenceNote && <small className="muted">{referenceNote}</small>}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div className="field">
                  <label htmlFor="a-tone">文风</label>
                  <select
                    className="creation-select"
                    id="a-tone"
                    onChange={(e) => setTone(e.target.value)}
                    value={tone}
                  >
                    <option value="">默认（自然中文）</option>
                    <option value="产品推广">产品推广</option>
                    <option value="技术解析">技术解析</option>
                    <option value="真人感">真人感增强</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="a-length">篇幅</label>
                  <select
                    className="creation-select"
                    id="a-length"
                    onChange={(e) => setLengthPreset(e.target.value)}
                    value={lengthPreset}
                  >
                    {LENGTH_OPTIONS.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {lengthPreset === "custom" && (
                <div className="field">
                  <label htmlFor="a-custom-length">自定义篇幅</label>
                  <input
                    id="a-custom-length"
                    onChange={(e) => setCustomLength(e.target.value)}
                    placeholder="例如：约 2000 字"
                    value={customLength}
                  />
                </div>
              )}
              <label className="creation-toolbar__choice">
                <input
                  checked={humanize}
                  onChange={(e) => setHumanize(e.target.checked)}
                  type="checkbox"
                />
                <span>启用真人感增强（humanizer-zh）</span>
              </label>
              <div>
                <button
                  className="button button--primary"
                  onClick={() => void startRun()}
                  type="button"
                >
                  <Plus size={16} />
                  开始创作
                </button>
              </div>
            </div>
          )}

          {!creating && runId && (
            <div>
              <span className="page-kicker">创作运行</span>
              <ol aria-label="创作事件" className="workflow-task__events" style={{ marginTop: 8 }}>
                {events.map((event) => {
                  const state = journalEventState(event.type);
                  const Icon = state === "failed" ? XCircle : state === "complete" ? Check : LoaderCircle;
                  return (
                    <li className={`is-${state}`} key={event.sequence}>
                      <Icon
                        aria-hidden="true"
                        className={state === "running" ? "spin" : undefined}
                        size={13}
                      />
                      <span>{journalEventMessage(event.type, event.payload)}</span>
                    </li>
                  );
                })}
              </ol>
              {running && (
                <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
                  <p className="muted" style={{ margin: 0 }}>
                    <LoaderCircle className="spin" size={14} /> 正在撰写正文……手动编辑会打断本次写回。
                  </p>
                  <button
                    className="button button--quiet"
                    onClick={() => {
                      if (runId) void bridge.stopArticleRun(runId);
                    }}
                    type="button"
                  >
                    停止
                  </button>
                </div>
              )}
              {!running && runFailed && (
                <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
                  <p className="muted" style={{ margin: 0 }}>失败上下文已保留，可以按当前要求重试。</p>
                  <button className="button button--quiet" onClick={() => void startRun()} type="button">
                    重试创作
                  </button>
                </div>
              )}
            </div>
          )}

          {!creating && !runId && selected && (
            <div style={{ display: "grid", gap: 10, maxWidth: assistantOpen ? "none" : 900, minWidth: 0 }}>
              <div className="field__head" style={{ padding: "0 2px" }}>
                <label htmlFor="a-markdown">正文（Markdown）</label>
                <span className="field-tag">
                  修订 {selected.currentRevisionId?.slice(0, 8)}
                </span>
              </div>
              <MarkdownWorkbench
                dirty={dirty}
                editorMode={viewMode}
                markdown={draft}
                onEditorModeChange={setViewMode}
                onImageFileDrop={uploadImageFile}
                onMarkdownChange={(markdown) => {
                  if (running && !userEditedRef.current) {
                    userEditedRef.current = true;
                    if (runId) void bridge.stopArticleRun(runId);
                  }
                  setDraft(markdown);
                }}
                onPendingImageInsertionHandled={() => setPendingInsertion(null)}
                onRequestSelectionRewrite={(sel) => {
                  setRewriteSelection(sel);
                  setRewriteOpen(true);
                }}
                pendingImageInsertion={pendingInsertion}
                previewPlatform={previewPlatform}
                onPreviewPlatformChange={setPreviewPlatform}
              />
              <div style={{ display: "flex", gap: 10 }}>
                {lastAiSnapshot && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    可撤销：{lastAiSnapshot.label}
                  </span>
                )}
                <button
                  className="text-button"
                  onClick={() => navigate("/")}
                  type="button"
                >
                  ← 返回工作台
                </button>
              </div>
            </div>
          )}

          {!creating && !runId && !selected && !loading && (
            <div className="empty-page">
              <FileText aria-hidden="true" size={28} />
              <p className="muted">从左侧选择文章，或点右上角 + 新建创作</p>
            </div>
          )}
        </div>
        {selected && !creating && assistantOpen && (
          <AssistantDrawer articleId={selected.articleId} markdown={draft} />
        )}
      </div>
      {selected && rewriteOpen && (
        <RewriteDialog
          articleId={selected.articleId}
          initialSelection={rewriteSelection}
          markdown={draft}
          onClose={() => {
            setRewriteOpen(false);
            setRewriteSelection(null);
          }}
          onApply={(next) => {
            setLastAiSnapshot({
              label: "AI 改写",
              markdown: draft,
              currentRevisionId: selected.currentRevisionId,
              contentHash: selected.contentHash,
            });
            if (rewriteSelection) {
              setDraft(
                draft.slice(0, rewriteSelection.start) +
                next +
                draft.slice(rewriteSelection.end),
              );
            } else {
              setDraft(next);
            }
            setRewriteOpen(false);
            setRewriteSelection(null);
          }}
        />
      )}
      {selected && visualPlan && (
        <div className="studio-modal__scrim" onClick={() => setVisualPlan(null)} role="presentation">
          <section aria-label="确认配图方案" aria-modal="true" role="dialog" style={{
            position: "fixed", inset: "12% 20%", background: "var(--surface, #fff)",
            borderRadius: 16, padding: "24px 28px", overflowY: "auto", zIndex: 60,
          }}>
            <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <span className="page-kicker">智能配图</span>
                <h2>确认配图方案（{visualPlan.placements.length} 张）</h2>
              </div>
              <button className="icon-button" onClick={() => setVisualPlan(null)} type="button">✕</button>
            </header>
            <p className="muted">
              素材库图片按匹配度自动选用；未达到阈值的位置将调用生图模型生成新图。
            </p>
            <ol style={{ display: "grid", gap: 10, marginTop: 12 }}>
              {visualPlan.placements.map((placement) => (
                <li key={placement.id} style={{ border: "1px solid var(--border, #ddd)", borderRadius: 12, padding: "10px 14px" }}>
                  <strong>{placement.anchorHeading ?? "文章正文"}</strong>
                  <span className="field-tag" style={{ marginLeft: 8 }}>
                    {placement.source === "existing_asset" ? "使用素材库" : "AI 生成"}
                  </span>
                  <small style={{ display: "block", marginTop: 4 }}>
                    {placement.selectionReason}｜alt：{placement.alt}
                  </small>
                  <div style={{ alignItems: "center", display: "flex", gap: 8, marginTop: 8 }}>
                    <button
                      className="button button--quiet"
                      onClick={() => setExcludedPlacementIds((current) =>
                        current.includes(placement.id)
                          ? current.filter((id) => id !== placement.id)
                          : [...current, placement.id])}
                      type="button"
                    >
                      {excludedPlacementIds.includes(placement.id) ? "保留这张" : "不插入这张"}
                    </button>
                    {excludedPlacementIds.includes(placement.id) && (
                      <small className="muted">确认应用时会跳过此位置。</small>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            <footer style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
              <button className="button button--quiet" onClick={() => setVisualPlan(null)} type="button">取消</button>
              <button
                className="button button--primary"
                disabled={visualBusy}
                onClick={() => void confirmVisualApply()}
                type="button"
              >
                {visualBusy ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}
                确认并插入配图
              </button>
            </footer>
          </section>
        </div>
      )}
      {selected && publishOpen && (
        <PublishDialog
          markdown={draft}
          onClose={() => setPublishOpen(false)}
          revisionId={selected.currentRevisionId ?? ""}
          title={selected.title}
        />
      )}
      {selected && historyOpen && (
        <RevisionHistoryDrawer
          articleId={selected.articleId}
          onClose={() => setHistoryOpen(false)}
          onRestored={() => {
            void loadArticles();
            void api
              .get<ArticleState>(`/articles/${selected.articleId}`)
              .then((res) => setSelected(res.data))
              .catch(() => undefined);
          }}
        />
      )}
      {selected && imagePickerOpen && (
        <ImagePickerDialog
          onClose={() => setImagePickerOpen(false)}
          onInsert={(markdownSnippet) => {
            setPendingInsertion(markdownSnippet);
            setImagePickerOpen(false);
          }}
        />
      )}
    </section>
  );
}

function ImagePickerDialog({
  onClose,
  onInsert,
}: {
  onClose: () => void;
  onInsert: (snippet: string) => void;
}) {
  const [assets, setAssets] = useState<Array<{ id: string; name: string; source: string; alt: string }>>([]);
  useEffect(() => {
    api
      .get<{ assets: Array<{ id: string; name: string; source: string; alt: string }> }>("/media")
      .then((res) => setAssets(res.data.assets))
      .catch(() => setAssets([]));
  }, []);

  return (
    <div className="studio-modal__scrim" onClick={onClose} role="presentation">
      <section
        aria-label="插入图片"
        aria-modal="true"
        className="creation-picker__dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        style={{ maxWidth: 560 }}
      >
        <header>
          <div>
            <span className="page-kicker">插入图片</span>
            <h2>从素材库选择</h2>
          </div>
          <button aria-label="关闭" className="icon-button" onClick={onClose} type="button">
            ×
          </button>
        </header>
        {assets.length === 0 ? (
          <p className="muted">素材库为空，请先到「素材库」上传或生成图片。</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, maxHeight: 380, overflowY: "auto" }}>
            {assets.map((asset) => (
              <button
                aria-label={`插入 ${asset.name}`}
                className="panel"
                key={asset.id}
                onClick={() =>
                  onInsert(`![${asset.alt || asset.name}](/api/media/${asset.id}/raw)`)
                }
                style={{ border: "1px solid var(--border)", borderRadius: 8, cursor: "pointer", padding: 6 }}
                type="button"
              >
                <img
                  alt={asset.alt || asset.name}
                  src={asset.source}
                  style={{ width: "100%", height: 90, objectFit: "cover", borderRadius: 6 }}
                />
                <small
                  className="muted"
                  style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {asset.name}
                </small>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
