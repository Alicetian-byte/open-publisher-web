export interface WorkflowNodeMeta {
  id: string;
  label: string;
  description: string;
}

/** 与后端 graph.py 中的节点保持一致，rewriter 属于优化循环。 */
export const WORKFLOW_NODES: WorkflowNodeMeta[] = [
  { id: "product_analyst", label: "产品理解", description: "提炼产品定位与卖点" },
  { id: "audience_analyst", label: "受众分析", description: "明确目标人群与痛点" },
  { id: "strategy_planner", label: "策略规划", description: "确定切入角度与结构" },
  { id: "copywriter", label: "推文生成", description: "产出多条候选推文" },
  { id: "critic", label: "质量评分", description: "多维度评审候选" },
  { id: "rewriter", label: "自动优化", description: "按评审意见改写" },
  { id: "safety_checker", label: "风险检查", description: "敏感内容与合规检查" },
  { id: "formatter", label: "平台格式化", description: "输出各平台版本" },
];
