// 配图位置操作工具：按行插入 / 按片段删除与移动，全部是纯函数。

export interface MarkdownSpan {
  /** 片段起始字符偏移（含）。 */
  start: number;
  /** 片段结束字符偏移（不含）。 */
  end: number;
}

function lineStartOf(markdown: string, offset: number): number {
  return offset === 0 ? 0 : markdown.lastIndexOf("\n", offset - 1) + 1;
}

/** 片段是否独占一行（整行去掉空白后与片段一致）。 */
function isOwnLine(markdown: string, span: MarkdownSpan): boolean {
  const lineStart = lineStartOf(markdown, span.start);
  const rawEnd = markdown.indexOf("\n", span.end);
  const lineEnd = rawEnd === -1 ? markdown.length : rawEnd;
  return markdown.slice(lineStart, lineEnd).trim() === markdown.slice(span.start, span.end).trim();
}

/** 片段所在行号（1 起）。 */
export function markdownLineOfOffset(markdown: string, offset: number): number {
  return markdown.slice(0, offset).split("\n").length;
}

/**
 * 把片段作为独立行插入到指定行（1 起）。
 * 行号超过总行数时追加到文末；会在前后补空行，保证片段独立成段。
 */
export function insertMarkdownAtLine(markdown: string, snippet: string, lineNumber: number): string {
  const endsWithNewline = markdown.endsWith("\n");
  const lines = markdown.split("\n");
  if (endsWithNewline && lines[lines.length - 1] === "") lines.pop();
  // 精确语义：片段占用用户指定的那一行，原内容整体下移，不做会错位的空行填充。
  const target = Math.max(1, Math.min(Math.floor(lineNumber) || 1, lines.length + 1));
  lines.splice(target - 1, 0, snippet);
  return lines.join("\n") + "\n";
}

/** 删除片段：独占一行时连同整行删除并收敛多余空行；行内片段只删片段本身。 */
export function removeMarkdownSpan(markdown: string, span: MarkdownSpan): string {
  if (!isOwnLine(markdown, span)) {
    return markdown.slice(0, span.start) + markdown.slice(span.end);
  }
  const lineStart = lineStartOf(markdown, span.start);
  const rawEnd = markdown.indexOf("\n", span.end);
  const lineEnd = rawEnd === -1 ? markdown.length : rawEnd + 1;
  return (markdown.slice(0, lineStart) + markdown.slice(lineEnd)).replace(/\n{3,}/g, "\n\n");
}

/**
 * 把片段移动到目标行（目标行号按移动前的文档计）。
 * 独占一行的配图整行搬走；行内配图只搬片段本身。
 */
export function moveMarkdownSpanToLine(markdown: string, span: MarkdownSpan, targetLine: number): string {
  const figureLine = markdownLineOfOffset(markdown, span.start);
  const ownLine = isOwnLine(markdown, span);
  const lineStart = lineStartOf(markdown, span.start);
  const rawEnd = markdown.indexOf("\n", span.end);
  const blockEnd = ownLine ? (rawEnd === -1 ? markdown.length : rawEnd + 1) : span.end;
  const block = ownLine
    ? markdown.slice(lineStart, rawEnd === -1 ? markdown.length : rawEnd).trim()
    : markdown.slice(span.start, span.end);
  if (!block) return markdown;

  const removedNewlines = markdown.slice(lineStart, blockEnd).split("\n").length - 1;
  const without = markdown.slice(0, lineStart) + markdown.slice(blockEnd);
  const adjusted = targetLine > figureLine ? targetLine - removedNewlines : targetLine;
  const moved = insertMarkdownAtLine(without, block, adjusted);
  return moved.replace(/\n{3,}/g, "\n\n");
}
