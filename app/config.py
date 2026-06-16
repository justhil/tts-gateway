from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    genie_host: str = "http://127.0.0.1:8429"
    characters_root: Path = Path("/www/genie/characters")
    refs_root: Path = Path("/www/genie/refs")
    data_dir: Path = Path("/data")
    character_models_file: str = "genie_character_models.json"
    character_mappings_file: str = "character_mappings.json"
    api_key: str = ""
    tts_timeout_sec: float = 600.0
    host: str = "0.0.0.0"
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()