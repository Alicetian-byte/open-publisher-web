"""一次性迁移脚本：把环境变量中的 API Key 加密写入 app_secrets。

企业级密钥存储上线（2026-10-26）后的存量迁移工具：
- 读取当前进程环境变量中的明文 key，用 SECRET_ENCRYPTION_KEY 加密入库；
- 迁移完成后，可从 .env / 部署环境中移除对应明文（环境变量仍保留为回退能力）；
- 幂等：重复执行会覆盖（key_version 自增），并写入审计。

用法（在 backend 目录下）：
  python scripts/migrate_env_keys_to_db.py             # 干跑：只显示计划
  python scripts/migrate_env_keys_to_db.py --execute   # 实际写入
  python scripts/migrate_env_keys_to_db.py --execute --skip-llm  # 只迁移生图 key

前置条件：
- 数据库已建表（alembic upgrade head，需含 0015_app_secrets）；
- SECRET_ENCRYPTION_KEY 已配置（未配置会拒绝执行，避免开发回退密钥入库）。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import secret_box  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import secret_store  # noqa: E402

MAPPINGS = {
    "LLM_API_KEY": secret_store.SECRET_ID_LLM_GLOBAL,
    "IMAGE_API_KEY": secret_store.SECRET_ID_IMAGE_GLOBAL,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="实际写入（缺省为干跑）")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM_API_KEY")
    parser.add_argument("--skip-image", action="store_true", help="跳过 IMAGE_API_KEY")
    args = parser.parse_args()

    if not (os.environ.get("SECRET_ENCRYPTION_KEY") or "").strip():
        print(
            "拒绝执行：SECRET_ENCRYPTION_KEY 未配置。\n"
            "生产环境必须显式配置主密钥（Fernet key）后再迁移，"
            "否则回退派生密钥会让入库密钥跟随 JWT 密钥轮换而失效。\n"
            "生成方式：python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        return 1

    plan = []
    skip = {"--skip-llm": "LLM_API_KEY", "--skip-image": "IMAGE_API_KEY"}
    for env_name, secret_id in MAPPINGS.items():
        if (args.skip_llm and env_name == "LLM_API_KEY") or (
            args.skip_image and env_name == "IMAGE_API_KEY"
        ):
            continue
        value = (os.environ.get(env_name) or "").strip()
        plan.append((env_name, secret_id, value))

    print("迁移计划（值只显示掩码）：")
    for env_name, secret_id, value in plan:
        state = "有值" if value else "为空，跳过"
        print(f"  {env_name} -> app_secrets[{secret_id}]  {state}")
    if not args.execute:
        print("干跑完成；确认无误后追加 --execute 执行。")
        return 0

    written = 0
    with SessionLocal() as db:
        for env_name, secret_id, value in plan:
            if not value:
                continue
            secret_store.set_secret(db, secret_id, value, actor="migrate-env-script")
            print(f"已写入 app_secrets[{secret_id}]：{secret_box.mask(value)}")
            written += 1
    print(f"完成：写入 {written} 条。现在可从 .env 中移除对应明文 key（保留变量名为回退）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
