import { useEffect, useState } from "react";

interface InsertPositionDialogProps {
  title: string;
  confirmLabel: string;
  /** 预填行号：插入默认 1，移动默认配图当前行。 */
  defaultLine: number;
  /** 可选预览内容（Markdown 片段或说明文字）。 */
  preview?: string;
  onConfirm: (lineNumber: number) => void;
  onClose: () => void;
}

/** 插入/移动位置的小窗口：输入正文行号，内容将作为该行独立插入。 */
export function InsertPositionDialog({
  title,
  confirmLabel,
  defaultLine,
  preview,
  onConfirm,
  onClose,
}: InsertPositionDialogProps) {
  const [lineText, setLineText] = useState(String(defaultLine));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const parsed = Number.parseInt(lineText, 10);
  const valid = Number.isFinite(parsed) && parsed >= 1;

  return (
    <div className="studio-modal" role="presentation">
      <div className="studio-modal__scrim" onClick={onClose} />
      <section
        aria-label={title}
        aria-modal="true"
        className="creation-picker__dialog"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        style={{ maxWidth: 380 }}
      >
        <header>
          <div>
            <span className="page-kicker">位置</span>
            <h2>{title}</h2>
          </div>
          <button aria-label="关闭" className="icon-button" onClick={onClose} type="button">
            ×
          </button>
        </header>
        {preview && (
          <p
            className="muted"
            style={{
              background: "var(--surface-muted)",
              borderRadius: 6,
              fontSize: 12,
              margin: "0 0 10px",
              maxHeight: 88,
              overflow: "hidden",
              padding: "6px 8px",
              wordBreak: "break-all",
            }}
          >
            {preview}
          </p>
        )}
        <label style={{ display: "grid", gap: 4 }}>
          <span>正文行号（第 1 行为文档首行）</span>
          <input
            autoFocus
            inputMode="numeric"
            min={1}
            onChange={(event) => setLineText(event.target.value.replace(/[^0-9]/g, ""))}
            onKeyDown={(event) => {
              if (event.key === "Enter" && valid) onConfirm(parsed);
            }}
            placeholder="如 3"
            style={{ width: "100%" }}
            type="number"
            value={lineText}
          />
        </label>
        <p className="muted" style={{ fontSize: 12, margin: "8px 0 12px" }}>
          内容会作为独立一行插入到该行位置；行号超过文末时插入到最后一行之后。
        </p>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="button button--quiet" onClick={onClose} type="button">
            取消
          </button>
          <button
            className="button button--primary"
            disabled={!valid}
            onClick={() => onConfirm(parsed)}
            type="button"
          >
            {confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
