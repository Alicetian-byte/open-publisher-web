export const ANNOUNCEMENT_REPOSITORY_URL = "https://github.com/tllovesxs/open-publisher";
export const ANNOUNCEMENT_RAW_BASE_URL = "https://raw.githubusercontent.com/tllovesxs/open-publisher/main/";

const MAX_REPOSITORY_PATH_LENGTH = 220;
const CONTROL_CHARACTERS = /[\u0000-\u001F\u007F]/;

export function isRepositoryMarkdownPath(value: string): boolean {
  if (!value || value.length > MAX_REPOSITORY_PATH_LENGTH || value !== value.trim()) return false;
  if (!value.startsWith("docs/") || !value.endsWith(".md")) return false;
  if (value.includes("\\") || value.includes("?") || value.includes("#")) return false;
  if (CONTROL_CHARACTERS.test(value)) return false;

  const segments = value.split("/");
  return segments.length >= 2
    && segments[0] === "docs"
    && segments.every((segment) => Boolean(segment) && segment !== "." && segment !== "..");
}

function encodedRepositoryPath(path: string): string | null {
  return isRepositoryMarkdownPath(path)
    ? path.split("/").map(encodeURIComponent).join("/")
    : null;
}

export function rawRepositoryMarkdownUrl(path: string): string | null {
  const encoded = encodedRepositoryPath(path);
  return encoded ? `${ANNOUNCEMENT_RAW_BASE_URL}${encoded}` : null;
}

export function githubRepositoryMarkdownUrl(path: string): string {
  const encoded = encodedRepositoryPath(path);
  return encoded
    ? `${ANNOUNCEMENT_REPOSITORY_URL}/blob/main/${encoded}`
    : ANNOUNCEMENT_REPOSITORY_URL;
}
