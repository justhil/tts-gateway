from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    genie_host: str = "http://127.0.0.1:8429"
    characters_root: Path = Path("/data/characters")
    refs_root: Path = Path("/data/refs")
    data_dir: Path = Path("/data/config")
    character_models_file: str = "genie_character_models.json"
    character_mappings_file: str = "character_mappings.json"
    api_key: str = ""
    tts_timeout_sec: float = 600.0
    host: str = "0.0.0.0"
    port: int = 8080
    refs_scan_max_depth: int = 2
    # Genie 跑在宿主机、网关跑在容器时：把扫描到的路径前缀换成 Genie 可见路径
    genie_path_prefix: str = ""
    genie_path_replace: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def path_for_genie(host_path: str) -> str:
    """容器内绝对路径 -> Genie 进程（宿主机）上的路径。"""
    s = get_settings()
    p, r = s.genie_path_prefix.strip(), s.genie_path_replace.strip()
    if not p or not r:
        return host_path
    if host_path.startswith(p):
        return r + host_path[len(p) :]
    return host_path