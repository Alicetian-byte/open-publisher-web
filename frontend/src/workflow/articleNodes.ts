export interface ArticleWorkflowNodeMeta {
  id: string;
  label: string;
  description: string;
}

/**
 * 文章创作工作流节点：与蓝本 WorkflowWorkspace 的 nodeLabel 一一对应
 * （research/outline/draft/natural-style/review/reference-safety/risk/visual）。
 * 前后节点由后端 writer_service 的 node.started/node.completed 事件驱动；
 * visual 节点的完成由前端配图阶段（visual-plan/visual-apply）确认。
 */
export const ARTICLE_WORKFLOW_NODES: ArticleWorkflowNodeMeta[] = [
  { id: "research", label: "资料整理", description: "汇总参考资料、素材与联网检索" },
  { id: "outline", label: "大纲规划", description: "生成结构化写作大纲" },
  { id: "draft", label: "正文撰写", description: "AI 按大纲流式撰写全文" },
  { id: "natural-style", label: "自然表达", description: "润色表达与文风" },
  { id: "review", label: "内容审阅", description: "审阅评分并按意见修订" },
  { id: "reference-safety", label: "资料核验", description: "核对断言与资料依据" },
  { id: "risk", label: "风险检查", description: "合规与敏感内容检查" },
  { id: "visual", label: "配图规划", description: "规划配图并插入正文" },
];

export function articleNodeLabel(nodeId: string | undefined | null): string {
  if (!nodeId) return "本次创作";
  return (
    ARTICLE_WORKFLOW_NODES.find((node) => node.id === nodeId)?.label ?? nodeId
  );
}
