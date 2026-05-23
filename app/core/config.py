from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "cales-backend"
    env: str = "dev"
    debug: bool = False

    # Cala.ai
    cala_base_url: str = "https://api.cala.ai"
    cala_api_key: str = ""
    use_cala_mock: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
