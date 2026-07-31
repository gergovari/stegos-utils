import re

with open("/tmp/steg_events.txt", "r") as f:
    lines = f.read().splitlines()

output = [
    "from dataclasses import dataclass",
    "from typing import Any, List, Dict, Optional",
    "",
    "@dataclass",
    "class StegEvent:",
    '    """Base class for all structured events."""',
    '    event_type: str = "unknown"',
    "",
    "    def to_dict(self) -> Dict[str, Any]:",
    "        return {k: v for k, v in self.__dict__.items() if k != 'event_type'}",
    ""
]

for line in lines:
    if not line or "grep:" in line or "If the command fails" in line:
        continue
    parts = line.split("|")
    event_name = parts[0].strip()
    args_str = parts[1].strip() if len(parts) > 1 else ""
    
    # generate class name
    class_name = "".join(x.capitalize() for x in event_name.split("_")) + "Event"
    
    # parse args
    args = []
    if args_str:
        # e.g. ", package=pkg, action=action, error=str(e"
        # Extract keys
        keys = re.findall(r'([a-zA-Z0-9_]+)=', args_str)
        args = keys
    
    output.append("@dataclass")
    output.append(f"class {class_name}(StegEvent):")
    output.append(f'    event_type: str = "{event_name}"')
    for arg in args:
        output.append(f"    {arg}: Any = None")
    
    output.append("")

with open("lib/steglib/event_types.py", "w") as f:
    f.write("\n".join(output))

