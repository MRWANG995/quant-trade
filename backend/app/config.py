from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./quant_trade.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: object) -> object:
        """Render 等托管平台默认给 'postgresql://...'，我们用 asyncpg 需要 '+asyncpg' 前缀。"""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v
    broker_mode: str = "paper"
    max_trades_per_day: int = 2
    max_trades_per_symbol_per_day: int = 1
    initial_capital: float = 100_000.0
    fast_ma: int = 20
    slow_ma: int = 50
    daily_run_cron: str = "0 22 * * 1-5"
    # 每日扫描默认不同步 yfinance（易限流）；本地已有 K 线即可扫描
    yfinance_sync_on_daily: bool = False
    yfinance_stale_days: int = 2
    yfinance_max_retries: int = 2
    yfinance_retry_base_seconds: float = 5.0
    yfinance_request_delay_seconds: float = 5.0

    stooq_api_key: str = ""
    alphavantage_api_key: str = ""
    # 真实源失败后自动用演示 K 线补全（无需任何 API Key 即可跑通）
    auto_demo_fallback: bool = True
    paper_slippage_bps: float = 5.0
    paper_commission_bps: float = 2.0

    # 无风险利率回退值（年化小数）。FRED 拉取失败且 DB 也无缓存时使用。
    default_risk_free_rate: float = 0.0

    # LLM（用于对话式策略生成）
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 1
    ib_account: str = ""

    oanda_api_key: str = ""
    oanda_account_id: str = ""
    oanda_env: str = "practice"

    cors_origins: list[str] = [
        "http://localhost:9998",
        "http://127.0.0.1:9998",
    ]
    # 正则形式的 CORS 白名单（用于 Vercel 等域名动态的场景）。
    # 例：'https://.*\.vercel\.app' 匹配 quant-trade.vercel.app 及所有预览 URL。
    cors_origin_regex: Optional[str] = None
    # 部署后填上前端公开地址，根 GET / 会重定向到这里。
    frontend_url: str = "http://localhost:9998"

    secret_key: str = "dev-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    require_auth: bool = False
    allow_registration: bool = True
    admin_email: str = ""
    admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
