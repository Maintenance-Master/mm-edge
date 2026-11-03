import logging
from threading import Event

from thingsboard_gateway.storage.event_storage import EventStorage
from thingsboard_gateway.storage.file.file_event_storage import FileEventStorage
from thingsboard_gateway.storage.memory.memory_event_storage import MemoryEventStorage
from thingsboard_gateway.storage.sqlite.sqlite_event_storage import SQLiteEventStorage
from thingsboard_gateway.tb_utility.tb_logger import TbLogger

_STORAGE_TYPES = {
    "memory": MemoryEventStorage,
    "file": FileEventStorage,
    "sqlite": SQLiteEventStorage
}

def create_event_storage(config: dict, main_stop_event: Event) -> EventStorage:
    storage_type = config.get("type", "sqlite").lower()

    storage_class = _STORAGE_TYPES.get(storage_type)

    if storage_class is None:
        supported = ", ".join(sorted(_STORAGE_TYPES.keys()))

        raise ValueError(f"Unsupported storage type: {storage_type}. Supported values: {supported}")

    logger = TbLogger(name="mm_edge.storage", level=logging.INFO)

    logger.info("Creating event storage: type=%s", storage_type)

    return storage_class(
        config,
        logger,
        main_stop_event
    )