import contextvars
from typing import Any

from steglib.event_types import StegEvent

# This holds the send function used by stegd to stream JSON to the client.
request_send_fn = contextvars.ContextVar('request_send_fn', default=None)

def emit(event: StegEvent):
    """Emit a structured event to the client stream.
    
    Args:
        event (StegEvent): The structured event object to emit.
    """
    send_fn = request_send_fn.get()
    if send_fn:
        send_fn({
            "type": "event",
            "event": event.event_type,
            "data": event.to_dict()
        })
    else:
        # Fallback if not running inside stegd (e.g., local tests or direct cli usage without daemon)
        import logging
        logger = logging.getLogger("steglib.events")
        # Do not format heavily, just debug so tests/cli can capture it if needed
        logger.debug("EVENT %s: %s", event.event_type, event.to_dict())
