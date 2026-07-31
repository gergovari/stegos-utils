import sys
sys.path.append("lib")
from steglib import event_types

all_events = [cls.event_type for name, cls in event_types.__dict__.items() if isinstance(cls, type) and issubclass(cls, getattr(event_types, 'StegEvent')) and cls is not getattr(event_types, 'StegEvent')]

with open("lib/steglib/client.py", "r") as f:
    client_code = f.read()

missing = []
for event_type in all_events:
    if f'"{event_type}"' not in client_code:
        missing.append(event_type)
        
print("Missing explicitly handled events:", missing)
