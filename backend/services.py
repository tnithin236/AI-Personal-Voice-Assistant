"""Service container: one instance of everything, created once per process. Heavy parts are lazy."""
import threading
from functools import lru_cache

from backend.brain.actions import PendingActions
from backend.brain.agent import Agent
from backend.brain.llm import LLM
from backend.config import Config
from backend.documents.document_processor import DocumentProcessor
from backend.memory.conversation import ConversationRepo, DocumentRepo
from backend.memory.database import Database, SettingsStore
from backend.memory.embeddings import Embedder
from backend.voice.audio_handler import Recorder
from backend.voice.speech_to_text import SpeechToText
from backend.voice.text_to_speech import TTSManager


class Services:
    def __init__(self):
        self.cfg = Config()
        self.cfg.ensure_dirs()
        self.db = Database(self.cfg.db_path)
        self.settings = SettingsStore(self.db, self.cfg.runtime_defaults())
        self.convo = ConversationRepo(self.db)
        self.documents_repo = DocumentRepo(self.db)
        self.embedder = Embedder(self.cfg.embedding_model, self.cfg.models_dir)
        self._vectors = None
        self._vec_lock = threading.Lock()
        self.llm = LLM(self.cfg, self.settings)
        self.stt = SpeechToText(self.cfg)
        self.tts = TTSManager(self.cfg, self.settings)
        self.recorder = Recorder()
        self.actions = PendingActions()
        self.documents = DocumentProcessor(lambda: self.vectors, self.documents_repo,
                                           self.cfg.chunk_size, self.cfg.chunk_overlap)
        self.agent = Agent(self)

    @property
    def vectors(self):
        """Embedded Qdrant (opened on first use; only ONE process may open the folder)."""
        with self._vec_lock:
            if self._vectors is None:
                from backend.memory.qdrant_store import VectorStore
                self._vectors = VectorStore(self.cfg.qdrant_path, self.embedder)
            return self._vectors

    @property
    def vectors_open(self) -> bool:
        return self._vectors is not None

    def ensure_conversation(self, cid: str | None) -> tuple[str, bool]:
        """Returns (conversation_id, created)."""
        if cid and self.convo.exists(cid):
            return cid, False
        return self.convo.create(), True

    def close(self) -> None:
        if self._vectors is not None:
            self._vectors.close()
        self.db.close()


@lru_cache(maxsize=1)
def get_services() -> Services:
    return Services()
