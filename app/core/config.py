from pydantic import AliasChoices, Field, model_validator
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
    hf_model_api_type: str = Field(default="", validation_alias=AliasChoices("hf_model_api_type", "HF_MODEL_API_TYPE"))
    hf_space_base_url: str = Field(
        default="https://ehubbarcelona-cales.hf.space/v1",
        validation_alias=AliasChoices("hf_space_base_url", "HF_SPACE_BASE_URL", "HF_MODEL_BASE_URL"),
    )
    hf_token: str = Field(default="", validation_alias=AliasChoices("hf_token", "HF_TOKEN", "HF_MODEL_API_KEY"))
    hf_model: str = Field(default="Qwen/Qwen2.5-32B-Instruct", validation_alias=AliasChoices("hf_model", "HF_MODEL", "HF_MODEL_NAME"))

    # Cala MCP (https://docs.cala.ai/integrations/mcp)
    cala_mcp_url: str = "https://api.cala.ai/mcp/"
    cala_mcp_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./cales.db"

    # Public base URL for absolute links in responses (e.g. PDF download URL).
    public_base_url: str = ""
    cors_origins: str = "*"
    report_storage_dir: str = ".cales_reports"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def infer_hf_provider(self) -> "Settings":
        if self.llm_provider == "groq" and self.hf_token and not self.groq_api_key:
            self.llm_provider = "hf"
        return self


settings = Settings()
