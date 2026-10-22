/** 质量评分报告：渲染 critic 产出的 quality_report artifact（blueprint 类体系）。 */

export interface QualityScores {
  clarity?: number;
  appeal?: number;
  relevance?: number;
  cta_strength?: number;
}

export interface QualityReview {
  candidate_id?: string;
  scores?: QualityScores;
  total?: number;
  issues?: string[];
  suggestions?: string[];
}

export interface QualityReportData {
  reviews?: QualityReview[];
  max_total?: number;
  pass?: boolean;
  threshold?: number;
}

const DIMENSIONS: { key: keyof QualityScores; label: string }[] = [
  { key: "clarity", label: "清晰度" },
  { key: "appeal", label: "吸引力" },
  { key: "relevance", label: "相关性" },
  { key: "cta_strength", label: "CTA 强度" },
];

function barColor(score: number | undefined): string {
  if (score == null) return "var(--surface-muted)";
  if (score >= 85) return "var(--success)";
  if (score >= 70) return "var(--warning)";
  return "var(--danger)";
}

export default function QualityReport({ report }: { report: QualityReportData }) {
  if (!report || !report.reviews?.length) {
    return null;
  }

  return (
    <section>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <span className="page-kicker">质量评分报告</span>
        <span
          className="article-status"
          style={
            report.pass
              ? { background: "var(--success-soft)", color: "var(--success)" }
              : { background: "var(--warning-soft)", color: "var(--warning)" }
          }
        >
          {report.pass ? "达标" : "未达标"}
        </span>
        <span className="article-status">
          最高 {Math.round(report.max_total ?? 0)} / 及格线 {report.threshold ?? "-"}
        </span>
      </div>

      <div style={{ marginTop: 8 }}>
        {report.reviews.map((review, idx) => (
          <article className="workflow-source-card" key={review.candidate_id ?? idx}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span className="article-status">候选 {review.candidate_id ?? `#${idx + 1}`}</span>
              <strong>{review.total != null ? Math.round(review.total) : "-"} 分</strong>
            </div>

            <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
              {DIMENSIONS.map(({ key, label }) => {
                const score = review.scores?.[key];
                return (
                  <div key={key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="page-kicker" style={{ width: 56, flexShrink: 0 }}>
                      {label}
                    </span>
                    <div
                      style={{
                        flex: 1,
                        height: 6,
                        borderRadius: 999,
                        background: "var(--surface-muted)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${Math.min(score ?? 0, 100)}%`,
                          height: "100%",
                          borderRadius: 999,
                          background: barColor(score),
                        }}
                      />
                    </div>
                    <span style={{ width: 28, textAlign: "right", fontSize: 11, color: "var(--muted)" }}>
                      {score != null ? Math.round(score) : "-"}
                    </span>
                  </div>
                );
              })}
            </div>

            {(review.issues?.length ?? 0) > 0 && (
              <ul style={{ margin: "8px 0 0", paddingLeft: 14, fontSize: 12, color: "var(--danger)" }}>
                {review.issues?.map((issue, i) => (
                  <li key={`issue-${i}`}>{issue}</li>
                ))}
              </ul>
            )}
            {(review.suggestions?.length ?? 0) > 0 && (
              <ul style={{ margin: "4px 0 0", paddingLeft: 14, fontSize: 12, color: "var(--muted)" }}>
                {review.suggestions?.map((s, i) => (
                  <li key={`sug-${i}`}>建议：{s}</li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
