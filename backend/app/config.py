from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    commission_percent: int = 10
    init_data_max_age: int = 86400  # сколько секунд живёт initData из Telegram
    dev_mode: bool = False  # вход без Telegram + тестовое пополнение. НЕ включать в проде


settings = Settings()
