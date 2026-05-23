from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "cales-backend"
    env: str = "dev"
    debug: bool = False

    # Cala.ai
    cala_base_url: str = "https://api.cala.ai"
    cala_api_key: str = ""
    use_cala_mock: bool = True

    # Agent LLM (Groq via OpenAI-compatible API)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    agent_model: str = "llama-3.1-8b-instant"

    # Cala MCP (https://docs.cala.ai/integrations/mcp)
    cala_mcp_url: str = "https://api.cala.ai/mcp/"
    cala_mcp_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./cales.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
