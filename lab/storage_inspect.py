import json
import logging
from threading import Event

from mm_edge.storage.event_storage_factory import create_event_storage

logging.basicConfig(level=logging.INFO)

with open("mm_edge/config/mm_gateway.json") as f:
    config = json.load(f)

stop_event = Event()

storage = create_event_storage(config=config["storage"], main_stop_event=stop_event)

try:
    print(f"Backlog before read: {storage.len()}")

    event_pack = storage.get_event_pack()

    print(f"Pack size: {len(event_pack)}")

    for index, event in enumerate(event_pack[:3], start=1):
        print(f"\n--- Event {index} ---")
        print(event)

    answer = input(
        "\nAcknowledge this pack and delete it from "
        "storage? [y/N]: "
    )

    if answer.strip().lower() == "y":
        storage.event_pack_processing_done()

        print(
            "Pack acknowledged. "
            f"Backlog now: {storage.len()}"
        )

    else:
        print(
            "Pack NOT acknowledged; "
            "events remain available."
        )
finally:
    stop_event.set()
    storage.stop()