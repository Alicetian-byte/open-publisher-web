import { createContext, useContext, useState, type ReactNode } from "react";
import { LoaderCircle, Sparkles } from "lucide-react";
import { api } from "../../api/client";

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

export interface VisualPlanSummary {
  targetCount: number;
  placements: VisualPlanPlacement[];
  sourceRevisionId: string | null;
  sourceContentHash: string | null;
  imageModelId?: string | null;
}

interface VisualApplyResult {
  article: {
    articleId: string;
    title: string;
    currentRevisionId: string | null;
    contentHash: string | null;
    markdown: string;
    updatedAt: string | null;
  };
  insertedCount: number;
  skipped: Array<{ id: string; reason: string }>;
}

export interface VisualPlanSnapshot {
  revisionId: string | null;
  contentHash: string | null;
  markdown: string;
}

interface VisualPlanJob {
  articleId: string;
  plan: VisualPlanSummary;
  snapshot: VisualPlanSnapshot | null;
}

interface CompletedVisualApply {
  articleId: string;
  article: VisualApplyResult["article"];
  snapshot: VisualPlanSnapshot;
  insertedCount: number;
  skipped: VisualApplyResult["skipped"];
}

interface StartVisualPlanOptions {
  targetCount?: number;
  assetIds?: string[];
  snapshot?: VisualPlanSnapshot | null;
}

interface VisualPlanContextValue {
  busy: boolean;
  error: string | null;
  job: VisualPlanJob | null;
  completed: CompletedVisualApply | null;
  excludedIds: string[];
  startPlan: (articleId: string, options?: StartVisualPlanOptions) => Promise<void>;
  setPlanForArticle: (
    articleId: string,
    plan: VisualPlanSummary,
    snapshot: VisualPlanSnapshot | null,
  ) => void;
  togglePlacement: (placementId: string) => void;
  closePlan: () => void;
  confirmApply: () => Promise<void>;
  consumeCompleted: () => void;
}

const VisualPlanContext = createContext<VisualPlanContextValue | null>(null);

function useVisualPlanContext(): VisualPlanContextValue {
  const value = useContext(VisualPlanContext);
  if (!value) throw new Error("useVisualPlan must be used within VisualPlanProvider");
  return value;
}

/** 智能配图任务的全局状态：
 * 确认弹窗和生图进度放在 App 级 Provider，切到其它页面也不会丢失进行中的任务。 */
export function VisualPlanProvider({ children }: { children: ReactNode }) {
  const [job, setJob] = useState<VisualPlanJob | null>(null);
  const [completed, setCompleted] = useState<CompletedVisualApply | null>(null);
  const [excludedIds, setExcludedIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startPlan = async (articleId: string, options: StartVisualPlanOptions = {}) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    setExcludedIds([]);
    try {
      const res = await api.post<VisualPlanSummary>(
        `/articles/${articleId}/visual-plan`,
        {
          targetCount: options.targetCount ?? 2,
          assetIds: options.assetIds ?? [],
        },
      );
      if (res.data.placements.length === 0) {
        setError("视觉规划认为本文不需要配图。");
        setJob(null);
        return;
      }
      setJob({
        articleId,
        plan: res.data,
        snapshot: options.snapshot ?? null,
      });
    } catch {
      setError("配图规划失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  const setPlanForArticle = (
    articleId: string,
    plan: VisualPlanSummary,
    snapshot: VisualPlanSnapshot | null,
  ) => {
    setJob({ articleId, plan, snapshot });
    setExcludedIds([]);
    setError(null);
  };

  const togglePlacement = (placementId: string) => {
    setExcludedIds((current) =>
      current.includes(placementId)
        ? current.filter((id) => id !== placementId)
        : [...current, placementId],
    );
  };

  const closePlan = () => {
    if (busy) return;
    setJob(null);
    setExcludedIds([]);
    setError(null);
  };

  const confirmApply = async () => {
    const current = job;
    if (!current || busy) return;
    const placements = current.plan.placements.filter(
      (placement) => !excludedIds.includes(placement.id),
    );
    if (!placements.length) {
      setError("请至少保留一张配图，或关闭方案。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let snapshot = current.snapshot;
      if (!snapshot) {
        const articleRes = await api.get<VisualApplyResult["article"]>(
          `/articles/${current.articleId}`,
        );
        snapshot = {
          revisionId: articleRes.data.currentRevisionId,
          contentHash: articleRes.data.contentHash,
          markdown: articleRes.data.markdown,
        };
      }
      const res = await api.post<VisualApplyResult>(
        `/articles/${current.articleId}/visual-apply`,
        {
          baseRevisionId: snapshot.revisionId,
          baseContentHash: snapshot.contentHash,
          placements,
          imageModelId: current.plan.imageModelId || null,
        },
      );
      if (!res.data.insertedCount) {
        const reason = res.data.skipped[0]?.reason;
        setError(reason ? `配图应用失败：${reason}` : "配图应用失败，请稍后重试。");
        return;
      }
      setCompleted({
        articleId: current.articleId,
        article: res.data.article,
        snapshot,
        insertedCount: res.data.insertedCount,
        skipped: res.data.skipped,
      });
      setJob(null);
      setExcludedIds([]);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "配图应用失败：文章可能已被修改，请刷新后重试。");
    } finally {
      setBusy(false);
    }
  };

  const consumeCompleted = () => setCompleted(null);

  return (
    <VisualPlanContext.Provider
      value={{
        busy,
        error,
        job,
        completed,
        excludedIds,
        startPlan,
        setPlanForArticle,
        togglePlacement,
        closePlan,
        confirmApply,
        consumeCompleted,
      }}
    >
      {children}
      {(job || (busy && !job)) && (
        <div className="studio-modal" role="presentation">
          <div className="studio-modal__scrim" />
          <section
            aria-label="确认配图方案"
            aria-modal="true"
            className="creation-picker__dialog"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            style={{ maxWidth: 560, width: "min(560px, 100%)" }}
          >
            <header style={{ alignItems: "center", display: "flex", justifyContent: "space-between" }}>
              <div>
                <span className="page-kicker">智能配图</span>
                <h2>{job ? `确认配图方案（${job.plan.placements.length} 张）` : "正在规划配图"}</h2>
              </div>
              <button
                aria-label="关闭配图方案"
                className="icon-button"
                disabled={busy}
                onClick={closePlan}
                type="button"
              >
                ✕
              </button>
            </header>
            {busy && (
              <p className="muted" style={{ alignItems: "center", display: "flex", gap: 8 }}>
                <LoaderCircle className="spin" size={15} />
                {job ? "正在生成并插入配图，可停留在当前页面等待；切换页面后进度不会丢失。" : "正在分析正文并规划配图，切换页面后进度不会丢失。"}
              </p>
            )}
            {error && (
              <div className="workflow-task__failure" role="alert" style={{ marginTop: 10 }}>
                <p>{error}</p>
              </div>
            )}
            <p className="muted">
              素材库图片按匹配度自动选用；未达到阈值的位置将调用生图模型生成新图。
            </p>
            <ol style={{ display: "grid", gap: 10, marginTop: 12 }}>
              {job?.plan.placements.map((placement) => (
                <li
                  key={placement.id}
                  style={{ border: "1px solid var(--border, #ddd)", borderRadius: 12, padding: "10px 14px" }}
                >
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
                      disabled={busy}
                      onClick={() => togglePlacement(placement.id)}
                      type="button"
                    >
                      {excludedIds.includes(placement.id) ? "保留这张" : "不插入这张"}
                    </button>
                    {excludedIds.includes(placement.id) && (
                      <small className="muted">确认应用时会跳过此位置。</small>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            <footer style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
              <button className="button button--quiet" disabled={busy} onClick={job ? closePlan : undefined} type="button">
                取消
              </button>
              <button
                className="button button--primary"
                disabled={busy}
                onClick={() => void confirmApply()}
                type="button"
              >
                {busy ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}
                {job ? "确认并插入配图" : "规划中…"}
              </button>
            </footer>
          </section>
        </div>
      )}
    </VisualPlanContext.Provider>
  );
}

export function useVisualPlan() {
  return useVisualPlanContext();
}
