"""Ringpuffer für die Live-Logs im Admin-Bereich.

Ein logging.Handler legt die letzten Einträge im Arbeitsspeicher ab (nichts wird auf die Platte geschrieben, nach einem
Neustart ist der Puffer leer; die vollständigen Logs liegen weiter in `docker compose logs`). Die Verwaltung liest den
Puffer inkrementell über die laufende Nummer `id` (siehe routers/admin_logs.py). Gilt pro Prozess: die App läuft mit
einem uvicorn-Worker.
"""
import itertools
import logging
import threading
from collections import deque
from datetime import datetime, timezone

MAX_ENTRIES = 2000
MAX_MESSAGE_CHARS = 2000
MAX_EXC_CHARS = 4000

# Technischer Dauerlärm: Healthcheck des Containers und die Log-Ansicht selbst
_NOISY_ACCESS_PREFIXES = ("/health", "/api/admin/logs")


def source_of(logger_name: str) -> str:
    """Grobe Herkunft für den Filter in der Oberfläche."""
    if logger_name == "uvicorn.access":
        return "access"
    if logger_name.startswith("app.chat"):
        return "chat"
    if logger_name.startswith("app.audit"):
        return "audit"
    if logger_name.startswith("uvicorn"):
        return "server"
    if logger_name.startswith("app"):
        return "app"
    return "system"


class LogBuffer:
    def __init__(self, max_entries: int = MAX_ENTRIES):
        self._entries: deque[dict] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def append(self, entry: dict) -> dict:
        with self._lock:
            entry = {"id": next(self._ids), **entry}
            self._entries.append(entry)
            return entry

    def since(self, after_id: int = 0, limit: int = 1000) -> list[dict]:
        """Einträge mit id > after_id, älteste zuerst. Bei after_id=0 die letzten `limit` (Rückblick beim Öffnen)."""
        with self._lock:
            if after_id <= 0:
                return list(self._entries)[-limit:]
            newer = [e for e in self._entries if e["id"] > after_id]
        return newer[:limit]

    def last_id(self) -> int:
        with self._lock:
            return self._entries[-1]["id"] if self._entries else 0

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class LogBufferHandler(logging.Handler):
    def __init__(self, buffer: "LogBuffer"):
        super().__init__(level=logging.DEBUG)
        self.buffer = buffer
        self.addFilter(self._drop_noise)

    @staticmethod
    def _drop_noise(record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access":
            args = record.args
            path = args[2] if isinstance(args, tuple) and len(args) >= 3 else ""
            return not str(path).startswith(_NOISY_ACCESS_PREFIXES)
        return True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            entry = {
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "logger": record.name,
                "source": source_of(record.name),
                "message": message[:MAX_MESSAGE_CHARS],
            }
            if record.exc_info:
                entry["exc"] = self.formatException(record.exc_info)[-MAX_EXC_CHARS:]
            self.buffer.append(entry)
        except Exception:  # Logging darf die Anwendung nie stören
            self.handleError(record)

    @staticmethod
    def formatException(exc_info) -> str:
        return logging.Formatter().formatException(exc_info)


log_buffer = LogBuffer()
_installed = False


def install_log_buffer(buffer: LogBuffer = log_buffer) -> None:
    """Hängt den Puffer an die Anwendungs- und uvicorn-Logger (einmalig, auch bei mehrfachem create_app())."""
    global _installed
    if _installed and buffer is log_buffer:
        return
    handler = LogBufferHandler(buffer)
    logging.getLogger().addHandler(handler)
    # Unter uvicorn propagieren "uvicorn" und "uvicorn.access" NICHT an root, dort hängt der Handler zusätzlich
    # (uvicorn.error läuft über "uvicorn"). Wo sie propagieren, erreicht der root-Handler sie bereits – sonst doppelte Einträge.
    for name in ("uvicorn", "uvicorn.access"):
        target = logging.getLogger(name)
        if not target.propagate:
            target.addHandler(handler)
    if buffer is log_buffer:
        _installed = True
