"""Central configuration. Static values come from .env (prefix VAANI_);
runtime-adjustable values live in SQLite and are seeded from RUNTIME_DEFAULTS."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), env_prefix="VAANI_", extra="ignore")

    app_name: str = "Vaani"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    data_dir: Path = ROOT / "data"

    # LLM
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "gemma3:4b"
    num_ctx: int = 4096
    num_gpu: int = -1
    max_tokens: int = 400
    temperature: float = 0.5
    keep_alive: str = "10m"

    # Speech
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute: str = "int8"
    whisper_beam: int = 1
    whisper_threads: int = 0  # 0 = library default
    piper_voice: str = "en_US-lessac-medium"
    piper_exe: str = ""
    tamil_tts_url: str = "http://127.0.0.1:8010"

    # Memory / documents
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 800
    chunk_overlap: int = 120
    max_upload_mb: int = 50

    @property
    def db_path(self) -> Path:
        return self.data_dir / "database" / "vaani.db"

    @property
    def qdrant_path(self) -> Path:
        return self.data_dir / "memory" / "qdrant"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_dirs(self) -> None:
        for p in (self.db_path.parent, self.qdrant_path, self.documents_dir, self.audio_dir,
                  self.models_dir, self.logs_dir):
            p.mkdir(parents=True, exist_ok=True)

    def runtime_defaults(self) -> dict:
        return {
            "language": "auto",          # auto | en | ta
            "llm_model": self.llm_model,
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
            "num_gpu": self.num_gpu,
            "max_tokens": self.max_tokens,
            "whisper_model": self.whisper_model,
            "mic_device": None,
            "piper_voice": self.piper_voice,
            "voice_speed": 1.0,
            "speak_replies": "voice",    # voice | always | never
            "use_memory": True,
            "auto_memory": True,
            "use_documents": True,
            "use_tools": True,
            "confirm_all_actions": False,
        }
