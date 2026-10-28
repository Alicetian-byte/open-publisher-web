"""微信公众号官方 API 发布通道（从零实现，基于微信开放文档）。

https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html

流程：access_token → 上传封面素材 → 创建草稿。
本模块只实现草稿模式（wechat_sync_draft），发布到粉丝时间线由用户在
微信后台确认后手动触发，避免误发。appid + appsecret 经 Fernet 加密
存入 app_secrets，与项目密钥约定一致。
"""

import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field
from io import BytesIO

import httpx
from sqlalchemy.orm import Session

from app.services import secret_store
from app.services.publish_outbox import PublishPlanError

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
WECHAT_SECRET_ID = "wechat:global"
_ACCESS_TOKEN_TTL_BUFFER = 120  # 提前 2 分钟刷新


@dataclass
class WeChatCredentials:
    app_id: str = ""
    app_secret: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.app_id.strip() and self.app_secret.strip())


def load_credentials(db: Session) -> WeChatCredentials:
    raw = secret_store.get_secret(db, WECHAT_SECRET_ID)
    if not raw:
        return WeChatCredentials()
    try:
        data = json.loads(raw)
        return WeChatCredentials(
            app_id=data.get("appId", ""), app_secret=data.get("appSecret", ""),
        )
    except (json.JSONDecodeError, TypeError):
        logger.warning("wechat:global 密钥 JSON 解析失败，按未配置处理")
        return WeChatCredentials()


def save_credentials(db: Session, *, app_id: str, app_secret: str, actor: str | None = None) -> None:
    payload = json.dumps({"appId": app_id.strip(), "appSecret": app_secret.strip()})
    secret_store.set_secret(db, WECHAT_SECRET_ID, payload, actor=actor)


def clear_credentials(db: Session, *, actor: str | None = None) -> None:
    secret_store.delete_secret(db, WECHAT_SECRET_ID, actor=actor)


# ---------- Markdown → HTML ----------

def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _inline(text: str) -> str:
    """处理行内元素：**bold**, *italic*, `code`, [link](url), ![alt](url)."""
    result = text
    result = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: f'<img src="{_escape_html(m.group(2))}" alt="{_escape_html(m.group(1))}" />',
        result,
    )
    result = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{_escape_html(m.group(2))}">{_escape_html(m.group(1))}</a>',
        result,
    )
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
    result = re.sub(r"\*(.+?)\*", r"<em>\1</em>", result)
    result = re.sub(r"`([^`]+)`", r"<code>\1</code>", result)
    return result


def markdown_to_wechat_html(markdown: str) -> str:
    """把 Markdown 转为微信公众号编辑器接受的 HTML。"""
    lines = markdown.strip().splitlines()
    html_parts: list[str] = []
    in_list = False
    in_code = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                html_parts.append("</code></pre>")
                in_code = False
            else:
                html_parts.append('<pre style="background:#f6f8fa;padding:12px;border-radius:6px;overflow-x:auto;"><code>')
                in_code = True
            continue

        if in_code:
            html_parts.append(_escape_html(line))
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append('<ul style="padding-left:20px;">')
                in_list = True
            html_parts.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        elif in_list:
            html_parts.append("</ul>")
            in_list = False

        heading_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            html_parts.append(f"<h{level}>{_inline(heading_match.group(2))}</h{level}>")
        elif stripped == "---":
            html_parts.append('<hr style="border:none;border-top:1px solid #ddd;margin:16px 0;" />')
        elif stripped.startswith("> "):
            html_parts.append(
                f'<blockquote style="border-left:3px solid #ddd;padding-left:12px;color:#666;">{_inline(stripped[2:])}</blockquote>'
            )
        elif not stripped:
            continue
        else:
            html_parts.append(f"<p>{_inline(stripped)}</p>")

    if in_list:
        html_parts.append("</ul>")
    if in_code:
        html_parts.append("</code></pre>")

    return "\n".join(html_parts)


# ---------- WeChat Official Delivery ----------

class WeChatOfficialDelivery:
    """蓝本 PublishOutboxService delivery 接口的微信实现。

    只创建草稿（draft/add），不自动发布到粉丝时间线。用户需要在
    微信后台确认草稿后手动发布，降低误操作风险。
    """

    def __init__(self, db: Session):
        self.db = db
        self._token_cache: dict = {}

    def _credentials(self) -> WeChatCredentials:
        creds = load_credentials(self.db)
        if not creds.configured:
            raise PublishPlanError(
                "微信公众号凭据未配置。请在管理端录入 appid 和 appsecret（加密入库）。"
            )
        return creds

    def _access_token(self) -> str:
        cached = self._token_cache.get("token")
        expires = self._token_cache.get("expires_at", 0)
        if cached and time.time() < expires:
            return cached

        creds = self._credentials()
        url = f"{WECHAT_API_BASE}/token"
        params = {"grant_type": "client_credential", "appid": creds.app_id, "secret": creds.app_secret}
        try:
            response = httpx.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise PublishPlanError(f"获取微信 access_token 失败：{exc}") from None

        token = data.get("access_token")
        if not token:
            errcode = data.get("errcode", "unknown")
            errmsg = data.get("errmsg", "no token")
            raise PublishPlanError(f"微信 API 返回错误 [{errcode}]: {errmsg}")

        expires_in = data.get("expires_in", 7200)
        self._token_cache = {
            "token": token,
            "expires_at": time.time() + expires_in - _ACCESS_TOKEN_TTL_BUFFER,
        }
        return token

    def _resolve_asset_data_url(self, asset_ref: str) -> tuple[bytes, str, str] | None:
        """解析 asset:// 或 data: URL 引用，返回 (bytes, mime, filename)。"""
        if asset_ref.startswith("asset://"):
            from app.models.media import MediaAsset
            asset_id = asset_ref[len("asset://"):]
            row = self.db.get(MediaAsset, asset_id)
            if row is None or not row.source.startswith("data:"):
                return None
            asset_ref = row.source
        if not asset_ref.startswith("data:"):
            return None

        try:
            header, b64_data = asset_ref.split("base64,", 1)
            mime = header.replace("data:", "").split(";")[0] or "image/png"
            content = base64.b64decode(b64_data)
        except Exception:
            return None

        ext = mime.split("/")[1] if "/" in mime else "png"
        ext = {"jpeg": "jpg"}.get(ext, ext)
        return content, mime, f"cover.{ext}"

    def _upload_cover(self, token: str, asset_ref: str | None, title: str) -> str | None:
        """上传封面图为永久素材，返回 media_id；无封面时返回 None。"""
        if not asset_ref:
            return None
        resolved = self._resolve_asset_data_url(asset_ref)
        if resolved is None:
            return None
        content, mime, filename = resolved

        url = f"{WECHAT_API_BASE}/material/add_material"
        params = {"access_token": token, "type": "image"}
        files = {"media": (filename, BytesIO(content), mime)}
        try:
            response = httpx.post(url, params=params, files=files, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("微信封面图上传失败（不影响草稿创建）: %s", exc)
            return None

        media_id = data.get("media_id")
        if not media_id:
            logger.warning("微信封面图上传返回无 media_id: %s", data)
            return None
        return media_id

    def _extract_cover_asset(self, markdown: str) -> str | None:
        """从 Markdown 的第一张图片提取素材引用作为封面。"""
        match = re.search(r"!\[[^\]]*\]\((asset://[^)]+|data:image/[^)]+)\)", markdown)
        return match.group(1) if match else None

    def _extract_summary(self, markdown: str, limit: int = 120) -> str:
        """从正文提取前几行作为摘要。"""
        for line in markdown.strip().splitlines():
            clean = re.sub(r"[#>*\-\[\]()!]", "", line).strip()
            if clean and len(clean) > 10:
                return clean[:limit]
        return title_fallback if (title_fallback := "") else ""

    def deliver(self, *, idempotency_key: str, platform: str, account_ref: str,
                title: str, markdown: str, mode: str) -> dict:
        if mode != "wechat_sync_draft":
            raise PublishPlanError(f"WeChatOfficialDelivery 收到不支持的投递模式: {mode}")
        if platform != "weixin":
            raise PublishPlanError(f"WeChatOfficialDelivery 只支持 weixin 平台，收到: {platform}")

        token = self._access_token()
        html_content = markdown_to_wechat_html(markdown)
        cover_asset = self._extract_cover_asset(markdown)
        thumb_media_id = self._upload_cover(token, cover_asset, title)
        digest = self._extract_summary(markdown)

        draft_url = f"{WECHAT_API_BASE}/draft/add"
        params = {"access_token": token}
        article: dict = {
            "title": title[:64],  # 微信限制 64 字符
            "content": html_content,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }
        if account_ref.strip():
            article["author"] = account_ref.strip()[:8]
        if digest:
            article["digest"] = digest[:120]
        if thumb_media_id:
            article["thumb_media_id"] = thumb_media_id

        try:
            response = httpx.post(draft_url, params=params, json={"articles": [article]}, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise PublishPlanError(f"微信草稿创建失败：{exc}") from None

        media_id = data.get("media_id")
        if not media_id:
            errcode = data.get("errcode", "unknown")
            errmsg = data.get("errmsg", "no media_id")
            raise PublishPlanError(f"微信草稿 API 返回错误 [{errcode}]: {errmsg}")

        return {
            "remoteId": media_id,
            "details": {
                "mode": mode,
                "platform": platform,
                "accountRef": account_ref,
                "title": article["title"],
                "draftOnly": True,
                "coverUploaded": thumb_media_id is not None,
                "notice": "草稿已创建到微信公众号后台。请在微信后台确认内容后手动发布到粉丝时间线。",
            },
        }

    def reconcile(self, *, idempotency_key: str, platform: str, mode: str) -> dict | None:
        """微信草稿 API 不支持按幂等键查询草稿，保持 UNKNOWN。"""
        return None
