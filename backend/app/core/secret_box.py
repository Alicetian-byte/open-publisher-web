"""对称加密信封（envelope encryption 的单机简化版）。

企业级约定：
- 主密钥（KEK）：环境变量 ``SECRET_ENCRYPTION_KEY``，Fernet 密钥格式
  （``cryptography.fernet.Fernet.generate_key()`` 生成）。只存在于进程
  环境变量 / 宿主密钥管理，不进数据库、不进仓库。
- 数据密文：Fernet token（AES-128-CBC + HMAC-SHA256），存数据库
  ``app_secrets`` 表；明文只在解密瞬间存在于进程内存。
- 不设开发回退：未配置专用主密钥时拒绝加密/解密，避免把 JWT 密钥
  复用为主密钥或在密钥轮换时破坏已入库密文。
- 轮换：换新主密钥后旧密文不可解，需重新录入或用迁移脚本重加密
  （key_version 记录版本，便于排查）。
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SecretBoxError(RuntimeError):
    """密钥信封相关错误（主密钥缺失/不合法、密文无法解密等）。"""


def generate_master_key() -> str:
    """生成一个新的 Fernet 主密钥（运维工具函数，供部署脚本使用）。"""
    return Fernet.generate_key().decode()


def get_fernet() -> Fernet:
    """解析当前主密钥；未显式配置专用密钥时直接失败。"""
    settings = get_settings()
    explicit = (settings.secret_encryption_key or "").strip()
    if not explicit:
        raise SecretBoxError(
            "SECRET_ENCRYPTION_KEY 未配置：API Key 只允许加密入库，"
            "必须先配置专用 Fernet 主密钥"
        )
    try:
        return Fernet(explicit.encode())
    except Exception as exc:  # noqa: BLE001 - 配置错误要给出清晰提示
        raise SecretBoxError(
            "SECRET_ENCRYPTION_KEY 不是合法的 Fernet 密钥；"
            "可用 python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\" 生成"
        ) from exc


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
