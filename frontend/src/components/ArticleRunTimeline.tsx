import { Check, LoaderCircle, XCircle } from "lucide-react";
import { ARTICLE_WORKFLOW_NODES } from "../workflow/articleNodes";

// 文章创作过程时间线：复刻蓝本 WorkflowWorkspace 的 workflow-timeline 类体系。
// 节点完成状态来自后端 node.completed 事件；配图节点由前端配图阶段驱动。

type NodeState = "pending" | "running" | "completed" | "failed";

interface ArticleRunTimelineProps {
  completedNodeIds: Iterable<string>;
  events?: Array<{ type?: string; eventType?: string; payload?: Record<string, unknown> }>;
  stopped?: boolean;
  runFailed?: boolean;
  /** "hidden"：本次创作不涉及配图，不渲染该节点。 */
  visualState?: "hidden" | "pending" | "running" | "done" | "failed";
}

function ArticleRunTimeline({ completedNodeIds, runFailed = false, visualState = "hidden", events = [], stopped = false }: ArticleRunTimelineProps) {
  const completed = new Set(completedNodeIds);
  const nodes = ARTICLE_WORKFLOW_NODES;
  let currentAssigned = false;
  const states: NodeState[] = nodes.map((node) => {
    if (node.id === "visual" && visualState !== "hidden") {
      if (visualState === "done") return "completed";
      if (visualState === "failed") return "failed";
      if (visualState === "running") return "running";
      if (!completed.has(node.id)) return "pending";
    }
    if (completed.has(node.id)) return "completed";
    if (runFailed) return "failed";
    if (stopped) return "pending";
    if (!currentAssigned) {
      currentAssigned = true;
      return "running";
    }
    return "pending";
  });

  return (
    <ol aria-label="创作流程进度" className="workflow-timeline">
      {nodes.map((node, i) => {
        const state = states[i];
        const detail = [...events].reverse().find(e => (e.type ?? e.eventType) === "node.completed" && e.payload?.nodeId === node.id)?.payload;
        const labels: Record<string, string> = { score: "评分", level: "风险等级", issues: "问题数", issueDetails: "具体意见", sections: "大纲章节", skipped: "已跳过", reason: "原因", mode: "模式", chars: "字数", changed: "已修改", ok: "核验通过", verdict: "审阅结论" };
        const reasons: Record<string, string> = { disabled: "用户已禁用", "manual-or-frontend-driven": "由配图工具继续处理", "no-draft": "没有可用正文", "no-references": "未提供参考资料", "output-invalid": "输出未通过校验" };
        return (
          <li
            className={`workflow-timeline__item${state === "running" ? " is-running" : ""}${state === "completed" ? " is-complete" : ""}`}
            key={node.id}
          >
            <span aria-hidden="true" className="workflow-timeline__icon">
              {state === "completed" ? (
                <Check size={14} />
              ) : state === "running" ? (
                <LoaderCircle className="spin" size={14} />
              ) : state === "failed" ? (
                <XCircle size={14} />
              ) : (
                <span style={{ fontSize: 11 }}>{i + 1}</span>
              )}
            </span>
            <div>
              <strong>{node.label}</strong>
              <small>{node.description}</small>
              {detail && <details><summary>{detail.skipped ? "已跳过 · 查看原因" : "查看结果"}</summary>
                <dl className="workflow-node-details">{Object.entries(detail).filter(([key]) => key !== "nodeId").map(([key, value]) => <div key={key}><dt>{labels[key] ?? key}</dt><dd>{Array.isArray(value) ? value.join("；") || "无" : typeof value === "boolean" ? value ? "是" : "否" : reasons[String(value)] ?? String(value)}</dd></div>)}</dl>
              </details>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default ArticleRunTimeline;
