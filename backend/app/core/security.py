"""认证安全工具：fastapi-users 密码散列（Argon2/Bcrypt）与旧版 PBKDF2 兼容。

- 新密码一律用 fastapi-users 默认 PasswordHelper（Argon2id）散列。
- 存量 `pbkdf2_sha256$...` 散列在登录时验证并自动升级为新散列。
- 旧版自研 HMAC 访问令牌仅保留解码能力，用于迁移期兜底；新令牌由
  fastapi-users 的 JWTStrategy 签发（标准 JWT）。
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi_users.password import PasswordHelper
from fastapi_users.password import PasswordHelperProtocol

from app.core.config import get_settings

LEGACY_PBKDF2_ITERATIONS = 390_000


# ---------------------------------------------------------------------------
# 旧版 PBKDF2（迁移期兼容，仅验证）
# ---------------------------------------------------------------------------


def verify_legacy_pbkdf2(password: str, password_hash: str) -> bool:
    """验证旧版 `pbkdf2_sha256$...` 散列；格式不符返回 False。"""
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# fastapi-users PasswordHelper：新散列走 Argon2，兼容旧 PBKDF2 并自动升级
# ---------------------------------------------------------------------------


class AppPasswordHelper(PasswordHelperProtocol):
    """fastapi-users PasswordHelper 适配：登录成功时把旧散列升级为 Argon2id。"""

    def __init__(self) -> None:
        self._modern = PasswordHelper()

    def hash(self, password: str) -> str:
        return self._modern.hash(password)

    def generate(self) -> str:
        return self._modern.generate()

    def verify_and_update(
        self, plain_password: str, hashed_password: str
    ) -> tuple[bool, str | None]:
        if hashed_password.startswith("pbkdf2_sha256$"):
            verified = verify_legacy_pbkdf2(plain_password, hashed_password)
            if not verified:
                return False, None
            # 升级为新散列（Argon2id），登录流程会将其写回数据库
            return True, self._modern.hash(plain_password)
        return self._modern.verify_and_update(plain_password, hashed_password)


password_helper = AppPasswordHelper()


# ---------------------------------------------------------------------------
# 旧版自研 HMAC 访问令牌（迁移期兜底解码；新令牌走 JWTStrategy）
# ---------------------------------------------------------------------------


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def decode_access_token(token: str) -> dict[str, Any]:
    """解码旧版自研令牌（payload.signature，HMAC-SHA256），仅供迁移期使用。"""
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64decode(payload_part)
        signature = _b64decode(signature_part)
        settings = get_settings()
        expected = hmac.new(
            settings.auth_jwt_secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("type") != "access" or int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expired")
        return payload
    except Exception as exc:
        raise ValueError("invalid access token") from exc

