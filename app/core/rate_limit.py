"""Einfacher Sliding-Window-Limiter im Arbeitsspeicher (je Prozess), z. B. für den öffentlichen Chat."""
import threading
import time


class RateLimiter:
    MAX_KEYS = 10_000  # Obergrenze gegen Speicherwachstum durch viele verschiedene Absender

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """True und Anfrage zählen, solange das Limit im Zeitfenster nicht erreicht ist."""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if t > cutoff]
            if len(hits) >= self.max_requests:
                self._hits[key] = hits
                return False
            if key not in self._hits and len(self._hits) >= self.MAX_KEYS:
                self._prune(cutoff)
                if len(self._hits) >= self.MAX_KEYS:
                    del self._hits[next(iter(self._hits))]
            hits.append(now)
            self._hits[key] = hits
            return True

    def _prune(self, cutoff: float) -> None:
        for key in list(self._hits):
            fresh = [t for t in self._hits[key] if t > cutoff]
            if fresh:
                self._hits[key] = fresh
            else:
                del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
