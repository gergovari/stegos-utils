import contextvars
from typing import Any

# This holds the send function used by stegd to stream JSON to the client.
request_send_fn = contextvars.ContextVar('request_send_fn', default=None)

def emit(event_type: str, **data: Any):
    """Emit a structured event to the client stream.
    
    Args:
        event_type (str): The semantic type of the event (e.g., 'package_installed').
        **data: Any additional metadata related to the event.
    """
    send_fn = request_send_fn.get()
    if send_fn:
        send_fn({
            "type": "event",
            "event": event_type,
            "data": data
        })
    else:
        # Fallback if not running inside stegd (e.g., local tests or direct cli usage without daemon)
        import logging
        logger = logging.getLogger("steglib.events")
        # Do not format heavily, just debug so tests/cli can capture it if needed
        logger.debug("EVENT %s: %s", event_type, data)
