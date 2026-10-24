import { useEffect, useMemo, useState } from "react";
import { BarChart3, ImageIcon, LoaderCircle, Plus, ScissorsLineDashed } from "lucide-react";
import { renderMermaidSvg } from "./MarkdownPreview";
import type { ImageInsertion } from "./MarkdownWorkbench";

const IMAGE_PATTERN = /!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
const MERMAID_PATTERN = /```mermaid[^\S\n]*\n([\s\S]*?)```/g;

export type ArticleFigure =
  | { kind: "image"; alt: string; src: string }
  | { kind: "mermaid"; source: string };

export function extractArticleFigures(markdown: string): ArticleFigure[] {
  const figures: ArticleFigure[] = [];
  for (const match of markdown.matchAll(MERMAID_PATTERN)) {
    const source = match[1]?.trim();
    if (source) figures.push({ kind: "mermaid", source });
  }
  for (const match of markdown.matchAll(IMAGE_PATTERN)) {
    const src = match[2];
    if (!src) continue;
    figures.push({ kind: "image", alt: match[1] || "", src });
  }
  return figures;
}

function MermaidThumb({ source, index }: { source: string; index: number }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setSvg(null);
    setFailed(false);
    renderMermaidSvg(`opw-figure-pane-${Date.now()}-${index}`, source)
      .then((next) => {
        if (!cancelled) setSvg(next);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [source, index]);
  if (failed) {
    return <div className="article-figures__mermaid is-error">图表渲染失败</div>;
  }
  if (svg === null) {
    return <div className="article-figures__mermaid is-loading">绘制中…</div>;
  }
  return (
    <div
      aria-label="文章图表缩略图"
      className="article-figures__mermaid"
      dangerouslySetInnerHTML={{ __html: svg }}
      role="img"
    />
  );
}

interface ArticleImagePaneProps {
  markdown: string;
  /** 在编辑器当前光标处插入 Markdown 片段（图片 / 图表均可）。 */
  onInsertAtCursor: (snippet: string) => void;
  onImageFileDrop?: (file: File) => Promise<ImageInsertion>;
  canInsert?: boolean;
}

/** 文章右侧配图栏：展示正文图片与创作生成的 mermaid 图表；
 * 上传的图片先进入"新上传素材"，点「插入」写入编辑器光标处。 */
export function ArticleImagePane({
  markdown,
  onInsertAtCursor,
  onImageFileDrop,
  canInsert = true,
}: ArticleImagePaneProps) {
  const figures = useMemo(() => extractArticleFigures(markdown), [markdown]);
  const [uploads, setUploads] = useState<ImageInsertion[]>([]);
  const [isDropping, setIsDropping] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const importFiles = async (files: File[]) => {
    if (!onImageFileDrop) {
      setError("图片上传服务尚未连接。");
      return;
    }
    const images = files.filter((file) => file.type.startsWith("image/"));
    if (!images.length) {
      setError("只能导入图片文件。");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const inserted = await Promise.all(images.map((file) => onImageFileDrop(file)));
      setUploads((current) => [...current, ...inserted]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "图片上传失败，请重试。");
    } finally {
      setUploading(false);
    }
  };

  const insertImage = (asset: ImageInsertion) => {
    onInsertAtCursor(`![${asset.alt}](${asset.src})`);
    setUploads((current) => current.filter((item) => item.src !== asset.src));
  };

  return (
    <aside
      aria-label="文章配图"
      className={`article-figures${isDropping ? " is-dropping" : ""}`}
      onDragEnter={(event) => {
        if (event.dataTransfer.types.includes("Files")) {
          event.preventDefault();
          setIsDropping(true);
        }
      }}
      onDragLeave={(event) => {
        if (event.currentTarget === event.target) setIsDropping(false);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        setIsDropping(false);
        void importFiles(Array.from(event.dataTransfer.files));
      }}
    >
      <header className="article-figures__head">
        <div className="article-figures__title">
          <ImageIcon size={15} />
          <span>配图</span>
          <span className="field-tag">{figures.length}</span>
        </div>
        {onImageFileDrop && (
          <label className="button button--quiet article-figures__upload">
            {uploading ? <LoaderCircle className="spin" size={14} /> : <Plus size={14} />}
            {uploading ? "上传中" : "上传"}
            <input
              accept="image/*"
              multiple
              onChange={(event) => {
                void importFiles(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
              style={{ display: "none" }}
              type="file"
            />
          </label>
        )}
      </header>

      <div className="article-figures__scroll">
        <p className="article-figures__section-label">正文配图与图表</p>
        {figures.length === 0 ? (
          <p className="article-figures__empty">
            正文还没有配图。创作生成的图表会显示在这里；也可以上传图片后插入到指定位置。
          </p>
        ) : (
          <div className="article-figures__grid">
            {figures.map((figure, index) => (
              <figure className="article-figures__item" key={`figure-${index}`}>
                {figure.kind === "image" ? (
                  <a href={figure.src} rel="noreferrer" target="_blank">
                    <img alt={figure.alt || `配图 ${index + 1}`} src={figure.src} />
                  </a>
                ) : (
                  <MermaidThumb index={index} source={figure.source} />
                )}
                <figcaption title={figure.kind === "image" ? figure.alt || figure.src : "创作生成的图表"}>
                  {figure.kind === "image"
                    ? figure.alt || `配图 ${index + 1}`
                    : `图表 ${index + 1}`}
                </figcaption>
              </figure>
            ))}
          </div>
        )}

        {onImageFileDrop && (
          <>
            <p className="article-figures__section-label">
              <ScissorsLineDashed size={12} /> 新上传素材
            </p>
            {uploads.length === 0 ? (
              <p className="article-figures__empty">
                拖入或上传的图片会先列在这里，点「插入」写入编辑器光标处。
              </p>
            ) : (
              <div className="article-figures__grid">
                {uploads.map((asset, index) => (
                  <figure className="article-figures__item" key={`${asset.src}-${index}`}>
                    <img alt={asset.alt} src={asset.src} />
                    <figcaption title={asset.alt}>{asset.alt}</figcaption>
                    {canInsert && (
                      <button
                        aria-label={`插入 ${asset.alt}`}
                        className="article-figures__insert"
                        onClick={() => insertImage(asset)}
                        title="插入到编辑器光标处"
                        type="button"
                      >
                        插入
                      </button>
                    )}
                  </figure>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      {error && (
        <p className="article-figures__error" role="alert">{error}</p>
      )}
      {figures.some((figure) => figure.kind === "mermaid") && (
        <p className="article-figures__hint">
          <BarChart3 size={12} /> 含创作生成的图表，会随正文实时更新
        </p>
      )}
    </aside>
  );
}
