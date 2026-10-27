"""对称加密信封（envelope encryption 的单机简化版）。

企业级约定：
- 主密钥（KEK）：环境变量 ``SECRET_ENCRYPTION_KEY``，Fernet 密钥格式
  （``cryptography.fernet.Fernet.generate_key()`` 生成）。只存在于进程
  环境变量 / 宿主密钥管理，不进数据库、不进仓库。
- 数据密文：Fernet token（AES-128-CBC + HMAC-SHA256），存数据库
  ``app_secrets`` 表；明文只在解密瞬间存在于进程内存。
- 开发回退：未配置 ``SECRET_ENCRYPTION_KEY`` 时从 ``AUTH_JWT_SECRET``
  派生主密钥，仅限本地开发与测试；生产部署必须显式配置专用密钥，
  否则 JWT 密钥轮换会连带导致已入库密钥全部不可解。
- 轮换：换新主密钥后旧密文不可解，需重新录入或用迁移脚本重加密
  （key_version 记录版本，便于排查）。
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SecretBoxError(RuntimeError):
    """密钥信封相关错误（主密钥缺失/不合法、密文无法解密等）。"""


def generate_master_key() -> str:
    """生成一个新的 Fernet 主密钥（运维工具函数，供部署脚本使用）。"""
    return Fernet.generate_key().decode()


def _derive_fallback_key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def get_fernet() -> Fernet:
    """解析当前主密钥；显式配置优先，未配置时回退 JWT 密钥派生（开发用）。"""
    settings = get_settings()
    explicit = (settings.secret_encryption_key or "").strip()
    if explicit:
        try:
            return Fernet(explicit.encode())
        except Exception as exc:  # noqa: BLE001 - 配置错误要给出清晰提示
            raise SecretBoxError(
                "SECRET_ENCRYPTION_KEY 不是合法的 Fernet 密钥；"
                "可用 python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\" 生成"
            ) from exc
    logger.warning(
        "SECRET_ENCRYPTION_KEY 未配置，回退从 AUTH_JWT_SECRET 派生主密钥"
        "（仅限开发环境；生产部署必须显式配置）"
    )
    return Fernet(_derive_fallback_key(settings.auth_jwt_secret))


def encrypt(plaintext: str) -> str:
    """明文 -> Fernet 密文（字符串）。"""
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """密文 -> 明文；主密钥不匹配时抛 SecretBoxError。"""
    try:
        return get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretBoxError(
            "密文无法解密：主密钥不匹配（SECRET_ENCRYPTION_KEY 与录入时不一致）"
        ) from exc


def mask(plaintext: str) -> str:
    """掩码提示：只保留末 4 位，供管理端展示（keyHint）。"""
    text = (plaintext or "").strip()
    if not text:
        return ""
    return f"****{text[-4:]}" if len(text) > 4 else "****"
