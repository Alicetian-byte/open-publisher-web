import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { marked } from "marked";
import DOMPurify from "dompurify";

export function renderMarkdown(markdown: string): string {
  return DOMPurify.sanitize(marked.parse(markdown, { async: false }) as string);
}

/* ---------------- AI 改写对话框（蓝本 RewriteService：只出候选，用户确认后应用） ---------------- */

interface RewriteDialogProps {
  articleId: string;
  markdown: string;
  onClose: () => void;
  onApply: (nextMarkdown: string, summary: string) => void;
  /** 蓝本 RewriteService：只针对选中文本出候选（不传则整篇）。 */
  initialSelection?: { start: number; end: number; text: string } | null;
}

export function RewriteDialog({ articleId, markdown, onClose, onApply, initialSelection = null }: RewriteDialogProps) {
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [candidate, setCandidate] = useState<{ replacements: string[]; summary: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    if (!instruction.trim()) {
      setError("请填写修改要求。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const run = await api.post<{ id: string }>("/agent-runs/rewrite-candidate", {
        articleId,
        markdown,
        instruction: instruction.trim(),
        selectedTexts: initialSelection?.text.trim() ? [initialSelection.text] : [],
      });
      // 轮询直到完成（改写通常只有一轮模型调用）
      for (let i = 0; i < 600; i += 1) {
        await new Promise((r) => setTimeout(r, 500));
        const status = await api.get<{ status: string }>(`/agent-runs/${run.data.id}`);
        if (status.data.status === "completed") {
          const events = await api.get<{ events: Array<{ type: string; payload: Record<string, unknown> }> }>(
            `/agent-runs/${run.data.id}/events?after=0`,
          );
          const ready = events.data.events.find((e) => e.type === "rewrite.candidate_ready");
          if (ready) {
            setCandidate({
              replacements: ready.payload.replacements as string[],
              summary: ready.payload.summary as string,
            });
          } else {
            setError("运行完成但没有候选结果。");
          }
          setBusy(false);
          return;
        }
        if (status.data.status === "failed" || status.data.status === "stopped") {
          setError("改写运行失败或已停止。");
          setBusy(false);
          return;
        }
      }
      setError("改写超时。");
      setBusy(false);
    } catch {
      setError("发起改写失败（需要后端配置 LLM Key）。");
      setBusy(false);
    }
  };

  const replaceWhole = (replacement: string) => onApply(replacement, candidate?.summary ?? "");

  return (
    <div className="studio-modal__scrim" onClick={onClose} role="presentation">
      <section
        aria-label="AI 改写"
        aria-modal="true"
        className="creation-picker__dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        style={{ maxWidth: 560 }}
      >
        <header>
          <div>
            <span className="page-kicker">AI 改写</span>
            <h2>只出候选，确认后才应用</h2>
          </div>
          <button aria-label="关闭" className="icon-button" onClick={onClose} type="button">
            ×
          </button>
        </header>
        {candidate ? (
          <div style={{ display: "grid", gap: 12 }}>
            <p className="muted">{candidate.summary}</p>
            <div className="field">
              <label>改写结果（整篇替换候选）</label>
              <textarea readOnly rows={12} value={candidate.replacements[0] ?? ""} />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="button button--primary"
                onClick={() => replaceWhole(candidate.replacements[0] ?? "")}
                type="button"
              >
                应用到编辑器
              </button>
              <button className="button button--quiet" onClick={() => setCandidate(null)} type="button">
                重新改写
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            <div className="field">
              <label htmlFor="rw-instruction">修改要求</label>
              <textarea
                id="rw-instruction"
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="例如：把开头改得更具体，去掉营销套话，保持事实不变"
                rows={4}
                value={instruction}
              />
            </div>
            {error && <p className="workflow-task__failure">{error}</p>}
            <div>
              <button className="button button--primary" disabled={busy} onClick={() => void start()} type="button">
                {busy ? "生成候选中……" : "生成改写候选"}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

/* ---------------- 发布工作台：多目标 → 审批 → 入队 → dry-run / unknown 处理 ---------------- */

interface PublishTarget {
  platform: string;
  accountRef: string;
  deliveryMode: "dry_run" | "wechat_sync_draft";
}

interface PublishJobView {
  id: string;
  planId: string;
  variantId: string;
  platform: string;
  accountRef: string;
  operation: string;
  state: string;
  remoteId: string | null;
  lastError: string | null;
  reconcileRequired: boolean;
}

interface PublishPlanView {
  planId: string;
  revisionId: string;
  status: string;
  approvalStatus: string;
  approvalBindingHash: string | null;
  variants: Array<{ id: string; platform: string; accountRef: string; title: string; contentHash: string }>;
  jobs: PublishJobView[];
}

interface PublishDialogProps {
  revisionId: string;
  title: string;
  markdown: string;
  onClose: () => void;
}

const PLATFORMS = ["twitter", "xiaohongshu", "wechat"];

export function PublishDialog({ revisionId, title, markdown, onClose }: PublishDialogProps) {
  const [targets, setTargets] = useState<PublishTarget[]>([
    { platform: "twitter", accountRef: "", deliveryMode: "dry_run" },
  ]);
  const [plan, setPlan] = useState<PublishPlanView | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const append = (line: string) => setLog((prev) => [...prev, line]);
  const message = (err: unknown, fallback: string) => {
    const detail = (err as { response?: { data?: { detail?: { message?: string } | string } } })
      ?.response?.data?.detail;
    return typeof detail === "object" && detail?.message ? detail.message : fallback;
  };

  const updateTarget = (index: number, patch: Partial<PublishTarget>) => {
    setTargets((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };

  const createPlan = async () => {
    const valid = targets.filter((target) => target.accountRef.trim());
    if (!valid.length) {
      setError("至少填写一个目标账号。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<PublishPlanView>("/publish/plans", {
        revisionId,
        title,
        markdown,
        targets: valid.map((target) => ({
          ...target,
          accountRef: target.accountRef.trim(),
        })),
      });
      setPlan(created.data);
      append(`计划已创建：${created.data.planId.slice(0, 20)}…`);
      append(`已绑定 ${created.data.variants.length} 个平台目标。`);
    } catch (err) {
      setError(message(err, "创建发布计划失败。"));
    } finally {
      setBusy(false);
    }
  };

  const approvePlan = async () => {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<PublishPlanView>(`/publish/plans/${plan.planId}/approve`, {
        actorId: "user:web",
      });
      setPlan(res.data);
      append(`已审批（绑定哈希 ${String(res.data.approvalBindingHash ?? "").slice(0, 18)}…）`);
    } catch (err) {
      setError(message(err, "审批失败：内容绑定可能已变化。"));
    } finally {
      setBusy(false);
    }
  };

  const enqueuePlan = async () => {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<PublishPlanView>(`/publish/plans/${plan.planId}/enqueue`);
      setPlan(res.data);
      append(`已入队 ${res.data.jobs.length} 个幂等任务。`);
    } catch (err) {
      setError(message(err, "入队失败：需要先通过审批。"));
    } finally {
      setBusy(false);
    }
  };

  const processPlan = async () => {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      let processed = 0;
      for (const job of plan.jobs.filter((item) => item.state === "pending")) {
        const res = await api.post<PublishPlanView>(`/publish/jobs/${job.id}/process`);
        setPlan(res.data);
        processed += 1;
      }
      append(`已处理 ${processed} 个 dry-run 任务。`);
    } catch (err) {
      setError(message(err, "处理任务失败。"));
    } finally {
      setBusy(false);
    }
  };

  const reconcile = async (job: PublishJobView) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<PublishPlanView>(`/publish/jobs/${job.id}/reconcile`);
      setPlan(res.data);
      append(`已核验 ${job.platform} 任务。`);
    } catch (err) {
      setError(message(err, "核验失败。"));
    } finally {
      setBusy(false);
    }
  };

  const resolveUnknown = async (job: PublishJobView, resolution: "draft_exists" | "draft_missing") => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<PublishPlanView>(`/publish/jobs/${job.id}/resolve-unknown`, {
        resolution,
      });
      setPlan(res.data);
      append(`已确认 ${job.platform} ${resolution === "draft_exists" ? "远端草稿存在" : "远端草稿缺失"}。`);
    } catch (err) {
      setError(message(err, "unknown 状态处理失败。"));
    } finally {
      setBusy(false);
    }
  };

  const jobStateLabel = (state: string) => ({
    pending: "待处理",
    in_progress: "处理中",
    succeeded: "成功",
    failed_retryable: "可重试失败",
    failed_terminal: "终态失败",
    unknown: "结果未知",
    reconciling: "核验中",
    cancelled: "已取消",
  }[state] ?? state);

  return (
    <div className="studio-modal__scrim" onClick={onClose} role="presentation">
      <section
        aria-label="发布工作台"
        aria-modal="true"
        className="creation-picker__dialog"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        style={{ maxWidth: 720 }}
      >
        <header>
          <div>
            <span className="page-kicker">发布工作台</span>
            <h2>多目标 Outbox</h2>
          </div>
          <button aria-label="关闭" className="icon-button" onClick={onClose} type="button">×</button>
        </header>

        <div style={{ display: "grid", gap: 14 }}>
          {!plan && (
            <>
              {targets.map((target, index) => (
                <div key={index} style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr 1fr", minWidth: 0 }}>
                  <label className="field"><span>平台</span>
                    <select
                      className="creation-select"
                      onChange={(event) => updateTarget(index, { platform: event.target.value })}
                      value={target.platform}
                    >
                      {PLATFORMS.map((platform) => <option key={platform} value={platform}>{platform}</option>)}
                    </select>
                  </label>
                  <label className="field"><span>账号标识</span>
                    <input
                      onChange={(event) => updateTarget(index, { accountRef: event.target.value })}
                      placeholder="@me"
                      value={target.accountRef}
                    />
                  </label>
                  <label className="field"><span>通道</span>
                    <select
                      className="creation-select"
                      onChange={(event) => updateTarget(index, {
                        deliveryMode: event.target.value as PublishTarget["deliveryMode"],
                      })}
                      value={target.deliveryMode}
                    >
                      <option value="dry_run">dry-run</option>
                      <option value="wechat_sync_draft">微信草稿</option>
                    </select>
                  </label>
                </div>
              ))}
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="button button--quiet"
                  disabled={targets.length >= 6}
                  onClick={() => setTargets((current) => [...current, {
                    platform: PLATFORMS[current.length % PLATFORMS.length]!,
                    accountRef: "",
                    deliveryMode: "dry_run",
                  }])}
                  type="button"
                >
                  添加目标
                </button>
                <button
                  className="button button--quiet"
                  disabled={targets.length <= 1}
                  onClick={() => setTargets((current) => current.slice(0, -1))}
                  type="button"
                >
                  移除最后目标
                </button>
                <button className="button button--primary" disabled={busy} onClick={() => void createPlan()} type="button">
                  {busy ? "创建中……" : "创建发布计划"}
                </button>
              </div>
            </>
          )}

          {plan && (
            <>
              <div className="panel" style={{ margin: 0, padding: 10 }}>
                <strong>计划状态：{plan.status}</strong>
                <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
                  审批：{plan.approvalStatus} · 绑定哈希 {plan.approvalBindingHash?.slice(0, 18) ?? "未生成"}…
                </p>
                <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                  <button className="button button--quiet" disabled={busy || plan.approvalStatus === "approved"} onClick={() => void approvePlan()} type="button">
                    审批计划
                  </button>
                  <button className="button button--quiet" disabled={busy || plan.approvalStatus !== "approved"} onClick={() => void enqueuePlan()} type="button">
                    入队
                  </button>
                  <button className="button button--quiet" disabled={busy || !plan.jobs.some((job) => job.state === "pending")} onClick={() => void processPlan()} type="button">
                    处理 pending
                  </button>
                </div>
              </div>

              <div aria-label="发布任务列表" style={{ display: "grid", gap: 8 }}>
                {plan.jobs.length === 0 && <p className="muted">还没有任务，先审批并入队。</p>}
                {plan.jobs.map((job) => (
                  <div className="panel" key={job.id} style={{ margin: 0, padding: 10 }}>
                    <div style={{ alignItems: "center", display: "flex", gap: 8, justifyContent: "space-between" }}>
                      <strong>{job.platform} · {job.accountRef}</strong>
                      <span className={job.state === "succeeded" ? "article-status article-status--published" : "article-status article-status--draft"}>
                        {jobStateLabel(job.state)}
                      </span>
                    </div>
                    <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
                      远端：{job.remoteId ?? "无"} {job.lastError ? ` · ${job.lastError}` : ""}
                    </p>
                    {(job.state === "unknown" || job.reconcileRequired) && (
                      <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                        <button className="button button--quiet" disabled={busy} onClick={() => void reconcile(job)} type="button">核验</button>
                        <button className="button button--quiet" disabled={busy} onClick={() => void resolveUnknown(job, "draft_exists")} type="button">远端已存在</button>
                        <button className="button button--quiet" disabled={busy} onClick={() => void resolveUnknown(job, "draft_missing")} type="button">远端缺失</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {log.length > 0 && (
            <ol aria-label="发布流程记录" className="workflow-task__events">
              {log.map((line, index) => <li key={index}><span>{line}</span></li>)}
            </ol>
          )}
          {error && <p className="workflow-task__failure">{error}</p>}
          <p className="muted">
            dry-run 不创建真实平台内容；微信草稿通道保留为可配置扩展，未知结果必须显式核验或人工 resolve。
          </p>
        </div>
      </section>
    </div>
  );
}

/* ---------------- 编辑助手抽屉：会话持久化 + 模型档案切换 ---------------- */

interface AssistantModelProfile {
  id: string;
  name: string;
  modelId: string;
  keyConfigured: boolean;
}

interface AssistantSessionMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  profileId?: string | null;
  createdAt?: string;
}

interface AssistantSessionView {
  id: string;
  articleId: string | null;
  title: string;
  activeProfileId: string | null;
  messages: AssistantSessionMessage[];
}

export function AssistantDrawer({
  articleId,
  markdown,
  selection = null,
  onApplySelection,
}: {
  articleId: string;
  markdown: string;
  selection?: { start: number; end: number; text: string } | null;
  onApplySelection?: (replacement: string) => void;
}) {
  const [session, setSession] = useState<AssistantSessionView | null>(null);
  const [messages, setMessages] = useState<AssistantSessionMessage[]>([]);
  const [profiles, setProfiles] = useState<AssistantModelProfile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string>("");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const attachmentsRef = useRef<HTMLInputElement>(null);
  const [attachments, setAttachments] = useState<string[]>([]);
  const [pendingSuggestion, setPendingSuggestion] = useState<string | null>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, busy]);

  useEffect(() => {
    let mounted = true;
    const bootstrap = async () => {
      try {
        const [profilesRes, sessionsRes] = await Promise.all([
          api.get<{ profiles: AssistantModelProfile[] }>("/settings/profiles"),
          api.get<{ sessions: AssistantSessionView[] }>(
            `/assistant/sessions?articleId=${encodeURIComponent(articleId)}`,
          ),
        ]);
        if (!mounted) return;
        setProfiles(profilesRes.data.profiles ?? []);
        const existing = sessionsRes.data.sessions?.[0] ?? null;
        if (existing) {
          setSession(existing);
          setMessages(existing.messages ?? []);
          setActiveProfileId(existing.activeProfileId ?? "");
        } else {
          const created = await api.post<AssistantSessionView>("/assistant/sessions", {
            articleId,
            title: "文章编辑助手",
          });
          if (!mounted) return;
          setSession(created.data);
          setMessages([]);
        }
      } catch {
        if (mounted) setError("助手会话加载失败；仍可发送，但本次不会持久化。");
      }
    };
    void bootstrap();
    return () => {
      mounted = false;
    };
  }, [articleId]);

  const send = async (options?: { mode?: "chat" | "rewrite"; message?: string }) => {
    const text = (options?.message ?? input).trim();
    const mode = options?.mode ?? "chat";
    if (!text || busy) return;
    const optimistic: AssistantSessionMessage = {
      id: `local-${Date.now()}`, role: "user", text,
    };
    setMessages((current) => [...current, optimistic]);
    setInput("");
    setAttachments([]);
    setBusy(true);
    setError(null);
    try {
      if (session) {
        const res = await api.post<AssistantSessionView & { reply: string }>(
          `/assistant/sessions/${session.id}/chat`,
          { message: text, articleContext: markdown, profileId: activeProfileId || null, mode, attachments },
        );
        setSession({
          ...res.data,
          messages: res.data.messages ?? [],
        });
        setMessages(res.data.messages ?? []);
        setActiveProfileId(res.data.activeProfileId ?? activeProfileId);
        if (mode === "rewrite") setPendingSuggestion(res.data.reply);
      } else {
        const res = await api.post<{ reply: string }>("/assistant/chat", {
          messages: [{ role: "user", text }],
          articleContext: markdown,
          profileId: activeProfileId || null,
          mode,
          attachments,
        });
        setMessages((current) => [
          ...current,
          { id: `assistant-${Date.now()}`, role: "assistant", text: res.data.reply },
        ]);
        if (mode === "rewrite") setPendingSuggestion(res.data.reply);
      }
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "助手调用失败（需要后端配置模型 Key）。");
    } finally {
      setBusy(false);
    }
  };

  const addAttachments = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const added: string[] = [];
    for (const file of Array.from(files)) {
      if (!file.type.startsWith("image/")) continue;
      if (file.size > 4 * 1024 * 1024) { setError("「" + file.name + "」超过 4MB，已跳过。"); continue; }
      if (attachments.length + added.length >= 4) break;
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
      added.push(dataUrl);
    }
    setAttachments((current) => [...current, ...added].slice(0, 4));
    if (attachmentsRef.current) attachmentsRef.current.value = "";
  };

  const clearSession = async () => {
    if (!session || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.delete(`/assistant/sessions/${session.id}`);
      const created = await api.post<AssistantSessionView>("/assistant/sessions", {
        articleId,
        title: "文章编辑助手",
      });
      setSession(created.data);
      setMessages([]);
    } catch {
      setError("清空会话失败。");
    } finally {
      setBusy(false);
    }
  };

  const activeProfile = profiles.find((profile) => profile.id === activeProfileId) ?? null;

  return (
    <aside
      aria-label="编辑助手"
      style={{
        display: "grid", gridTemplateRows: "auto auto 1fr auto", gap: 10,
        width: 320, borderLeft: "1px solid var(--border)", padding: 16,
        background: "var(--surface)", overflowY: "auto",
      }}
    >
      <div>
        <span className="page-kicker">编辑助手</span>
        <p className="muted" style={{ fontSize: 11 }}>只给建议，不直接改文章</p>
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        <select
          aria-label="助手模型"
          className="creation-select"
          disabled={profiles.length === 0}
          onChange={(event) => setActiveProfileId(event.target.value)}
          value={activeProfileId || ""}
        >
          <option value="">默认模型</option>
          {profiles.map((profile) => (
            <option key={profile.id} value={profile.id}>
              {profile.name} · {profile.modelId}{profile.keyConfigured ? "" : "（缺少密钥）"}
            </option>
          ))}
        </select>
        <div style={{ alignItems: "center", display: "flex", gap: 6 }}>
          <small className="muted" style={{ flex: 1 }}>
            {session ? `会话 ${session.id.slice(0, 8)}…已持久化` : "会话未加载"}
          </small>
          <button className="text-button" disabled={!session || busy} onClick={() => void clearSession()} type="button">
            清空
          </button>
        </div>
        {activeProfile && !activeProfile.keyConfigured && (
          <small style={{ color: "var(--warning)", fontSize: 11 }}>当前档案缺少服务端密钥。</small>
        )}
      </div>
      <div ref={listRef} style={{ display: "grid", gap: 8, alignContent: "start", overflowY: "auto" }}>
        {messages.length === 0 && (
          <p className="muted" style={{ fontSize: 12 }}>
            例如：「帮我检查开头是否有营销套话」「这三段的顺序怎么调更好」
          </p>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            style={{
              padding: "8px 10px", borderRadius: 8, fontSize: 12, lineHeight: 1.6,
              background: message.role === "user"
                ? "var(--accent-soft)"
                : "var(--surface-raised, var(--surface))",
              whiteSpace: "pre-wrap",
            }}
          >
            {message.text}
          </div>
        ))}
        {busy && <p className="muted" style={{ fontSize: 12 }}>思考中……</p>}
        {error && <p className="workflow-task__failure" style={{ fontSize: 12 }}>{error}</p>}
      </div>
      {pendingSuggestion && (
        <div style={{ background: "var(--accent-soft)", borderRadius: 8, display: "grid", fontSize: 12, gap: 8, padding: 10 }}>
          <strong>改写建议</strong>
          <div style={{ maxHeight: 160, overflowY: "auto", whiteSpace: "pre-wrap" }}>{pendingSuggestion}</div>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className="button button--primary"
              onClick={() => { onApplySelection?.(pendingSuggestion); setPendingSuggestion(null); }}
              type="button"
            >
              应用到文章
            </button>
            <button className="button button--quiet" onClick={() => setPendingSuggestion(null)} type="button">忽略</button>
          </div>
        </div>
      )}
      {selection?.text.trim() ? (
        <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
          <small className="muted" style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            已选中 {selection.text.length} 字
          </small>
          <button
            className="button button--quiet"
            disabled={busy}
            onClick={() => void send({ mode: "rewrite", message: input.trim() || "润色这段文字，保持原有语气" })}
            type="button"
          >
            改写选中片段
          </button>
        </div>
      ) : null}
      <div style={{ display: "grid", gap: 6 }}>
        <textarea
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
          placeholder="问点什么……（Enter 发送）"
          rows={3}
          value={input}
        />
        {attachments.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {attachments.map((dataUrl, index) => (
              <div key={index} style={{ position: "relative" }}>
                <img alt={`附件 ${index + 1}`} src={dataUrl} style={{ borderRadius: 6, height: 44, objectFit: "cover", width: 60 }} />
                <button
                  aria-label={`移除附件 ${index + 1}`}
                  className="icon-button"
                  onClick={() => setAttachments((current) => current.filter((_, i) => i !== index))}
                  style={{ position: "absolute", right: -6, top: -6 }}
                  type="button"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        <div style={{ alignItems: "center", display: "flex", gap: 6 }}>
          <button className="text-button" disabled={attachments.length >= 4} onClick={() => attachmentsRef.current?.click()} type="button">
            附加图片（≤4 张，需模型支持图片理解）
          </button>
          <input
            accept="image/*"
            hidden
            multiple
            onChange={(event) => void addAttachments(event.target.files)}
            ref={attachmentsRef}
            type="file"
          />
        </div>
        <small className="muted" style={{ fontSize: 10 }}>
          上下文：当前编辑器正文；模型由服务端档案决定。
        </small>
      </div>
    </aside>
  );
}


/* ---------------- 版本历史抽屉：列表 + 恢复旧版本为新修订 ---------------- */

interface RevisionListItem {
  revisionId: string;
  revisionNumber: number;
  title: string;
  contentHash: string;
  createdAt: string;
  reason: string;
  isCurrent: boolean;
}

export function RevisionHistoryDrawer({
  articleId,
  onClose,
  onRestored,
}: {
  articleId: string;
  onClose: () => void;
  onRestored?: () => void;
}) {
  const [revisions, setRevisions] = useState<RevisionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api
      .get<{ revisions: RevisionListItem[] }>(`/articles/${encodeURIComponent(articleId)}/revisions`)
      .then((res) => {
        if (mounted) setRevisions(res.data.revisions ?? []);
      })
      .catch(() => {
        if (mounted) setError("无法加载版本历史。");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [articleId]);

  const restore = async (revisionId: string) => {
    setRestoring(revisionId);
    setError(null);
    try {
      await api.post(`/articles/${encodeURIComponent(articleId)}/revisions/${revisionId}/restore`);
      onRestored?.();
      onClose();
    } catch {
      setError("恢复失败：文章可能已被修改，请刷新后重试。");
    } finally {
      setRestoring(null);
    }
  };

  return (
    <div className="studio-modal__scrim" onClick={onClose} role="presentation">
      <section
        aria-label="版本历史"
        aria-modal="true"
        className="creation-picker__dialog"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        style={{ maxWidth: 620 }}
      >
        <header>
          <div>
            <span className="page-kicker">历史</span>
            <h2>版本记录</h2>
          </div>
          <button aria-label="关闭" className="icon-button" onClick={onClose} type="button">×</button>
        </header>
        <div style={{ display: "grid", gap: 8, maxHeight: 480, overflowY: "auto" }}>
          {loading && <p className="muted">加载中……</p>}
          {!loading && revisions.length === 0 && <p className="muted">还没有版本记录。</p>}
          {revisions.map((revision) => (
            <div className="panel" key={revision.revisionId} style={{ margin: 0, padding: 10 }}>
              <div style={{ alignItems: "center", display: "flex", gap: 8, justifyContent: "space-between" }}>
                <strong>#{revision.revisionNumber} {revision.title}</strong>
                {revision.isCurrent ? (
                  <span className="article-status article-status--published">当前</span>
                ) : (
                  <button
                    className="button button--quiet"
                    disabled={restoring === revision.revisionId}
                    onClick={() => void restore(revision.revisionId)}
                    type="button"
                  >
                    {restoring === revision.revisionId ? "恢复中……" : "恢复"}
                  </button>
                )}
              </div>
              <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
                {new Date(revision.createdAt).toLocaleString()} · {revision.reason || "无说明"}
              </p>
            </div>
          ))}
          {error && <p className="workflow-task__failure">{error}</p>}
        </div>
      </section>
    </div>
  );
}
