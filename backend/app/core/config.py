from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Open Publisher Web"
    app_env: str = "development"
    database_url: str = (
        "mysql+pymysql://opw:opw_password@localhost:3306/"
        "open_publisher_web?charset=utf8mb4"
    )
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    # 登录认证（管理站与用户站共用账号后端；令牌签名密钥用环境变量配置）
    auth_jwt_secret: str = "dev-open-publisher-web-secret-change-me"
    access_token_expire_minutes: int = 720
    auth_admin_username: str = "admin"
    # 默认只是占位符：必须通过 AUTH_ADMIN_PASSWORD 配置真实管理员密码（不进仓库）
    auth_admin_password: str = "change_me_admin_password"
    auth_admin_display_name: str = "系统管理员"


    # LLM（OpenAI 兼容接口；密钥支持 DB 加密存储 app_secrets，环境变量仅作回退/开发）
    # 兼容 LLM_API_KEY 与 OPENAI_API_KEY 两种命名（后者为 .env.example 中的习惯写法）
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL"),
    )
    llm_timeout_seconds: int = 120

    # 生图链路：独立于文本 LLM，未显式配置时回退 LLM_* / OPENAI_*
    image_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("IMAGE_API_KEY", "OPENAI_IMAGE_API_KEY"),
    )
    image_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("IMAGE_BASE_URL", "OPENAI_IMAGE_BASE_URL"),
    )
    image_model: str = Field(
        default="gpt-image-1",
        validation_alias=AliasChoices("IMAGE_MODEL", "OPENAI_IMAGE_MODEL"),
    )
    image_timeout_seconds: int = Field(
        default=180,
        validation_alias=AliasChoices("IMAGE_TIMEOUT_SECONDS", "OPENAI_IMAGE_TIMEOUT_SECONDS"),
    )

    # 密钥信封主密钥（KEK）：Fernet 密钥，加密 app_secrets 中的密钥密文。
    # 生产必须显式配置；未配置时开发回退从 auth_jwt_secret 派生。
    secret_encryption_key: str = Field(
        default="",
        validation_alias=AliasChoices("SECRET_ENCRYPTION_KEY", "SECRET_MASTER_KEY"),
    )

    # 工作流
    workflow_score_threshold: int = 80
    workflow_max_iterations: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

