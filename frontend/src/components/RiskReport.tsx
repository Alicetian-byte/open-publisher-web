/** 风险报告：渲染 safety_report artifact（blueprint 类体系）。 */

export interface RiskIssue {
  type?: string;
  text?: string;
  suggestion?: string;
}

export interface RiskCheck {
  candidate_id?: string;
  level?: string;
  issues?: RiskIssue[];
}

export interface SafetyReport {
  overall_level?: string;
  checks?: RiskCheck[];
}

function riskChipStyle(level?: string): React.CSSProperties {
  if (level === "high") return { background: "var(--danger-soft)", color: "var(--danger)" };
  if (level === "medium") return { background: "var(--warning-soft)", color: "var(--warning)" };
  return { background: "var(--success-soft)", color: "var(--success)" };
}

function levelLabel(level?: string): string {
  if (level === "high") return "高风险";
  if (level === "medium") return "中风险";
  return "低风险";
}

export default function RiskReport({ report }: { report: SafetyReport }) {
  if (!report || (!report.checks?.length && !report.overall_level)) {
    return null;
  }

  const hasIssues = report.checks?.some((check) => (check.issues?.length ?? 0) > 0);

  return (
    <section>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <span className="page-kicker">风险检查报告</span>
        <span className="article-status" style={riskChipStyle(report.overall_level)}>
          整体 {levelLabel(report.overall_level)}
        </span>
        {!hasIssues && <span className="article-status">未发现问题</span>}
      </div>

      <div style={{ marginTop: 8 }}>
        {report.checks?.map((check, idx) => (
          <article className="workflow-source-card" key={check.candidate_id ?? idx}>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <span className="article-status">候选 {check.candidate_id ?? `#${idx + 1}`}</span>
              <span className="article-status" style={riskChipStyle(check.level)}>
                {levelLabel(check.level)}
              </span>
            </div>

            {(check.issues?.length ?? 0) === 0 ? (
              <p className="page-kicker" style={{ marginTop: 6 }}>
                无问题。
              </p>
            ) : (
              <ul style={{ margin: "8px 0 0", paddingLeft: 0, display: "grid", gap: 6, fontSize: 12 }}>
                {check.issues?.map((issue, i) => (
                  <li key={i} style={{ listStyle: "none" }}>
                    <strong style={{ color: "var(--ink)" }}>[{issue.type ?? "问题"}]</strong>{" "}
                    <span style={{ color: "var(--ink-soft)" }}>{issue.text}</span>
                    {issue.suggestion && (
                      <span style={{ color: "var(--muted)" }}> → 建议：{issue.suggestion}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
