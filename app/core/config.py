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

    # HF Space TGI (OpenAI-compatible). Set llm_provider="hf" to use this.
    # Auth: hf_token is the HF user token (read scope is enough for private Space).
    llm_provider: str = "groq"  # "groq" | "hf"
    hf_space_base_url: str = "https://ehubbarcelona-cales.hf.space/v1"
    hf_token: str = ""
    hf_model: str = "Qwen/Qwen2.5-32B-Instruct"

    # Cala MCP (https://docs.cala.ai/integrations/mcp)
    cala_mcp_url: str = "https://api.cala.ai/mcp/"
    cala_mcp_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./cales.db"

    # Public base URL for absolute links in responses (e.g. PDF download URL).
    public_base_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
