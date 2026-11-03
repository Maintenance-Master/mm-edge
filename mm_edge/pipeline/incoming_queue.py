from queue import Queue
from typing import Any

class IncomingTelemetryQueue:
    def __init__(self, max_size: int = 10000):
        self._queue = Queue(maxsize=max_size)

    def put_nowait(self, connector_name: str, connector_id: str, data: Any,) -> None:
        self._queue.put_nowait(
            (connector_name, connector_id, data)
        )

    def get(self, timeout: float | None = None):
        return self._queue.get(timeout=timeout)

    def task_done(self) -> None:
        self._queue.task_done()

    def size(self) -> int:
        return self._queue.qsize()