import re

with open("/tmp/steg_events.txt", "r") as f:
    lines = f.read().splitlines()

event_dict = {}

for line in lines:
    if not line or "grep:" in line or "If the command fails" in line:
        continue
    parts = line.split("|")
    event_name = parts[0].strip()
    args_str = parts[1].strip() if len(parts) > 1 else ""
    
    keys = re.findall(r'([a-zA-Z0-9_]+)=', args_str)
    
    if event_name not in event_dict:
        event_dict[event_name] = set()
    for k in keys:
        event_dict[event_name].add(k)

output = [
    "from dataclasses import dataclass",
    "from typing import Any, Dict",
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

for event_name in sorted(event_dict.keys()):
    class_name = "".join(x.capitalize() for x in event_name.split("_")) + "Event"
    output.append("@dataclass")
    output.append(f"class {class_name}(StegEvent):")
    output.append(f'    event_type: str = "{event_name}"')
    
    keys = sorted(list(event_dict[event_name]))
    if not keys:
        pass
    for k in keys:
        if k in ('message', 'error', 'details', 'line', 'output', 'count', 'command', 'provider', 'dependents', 'path', 'group', 'instances', 'targets', 'available', 'consumer', 'missing_provider', 'force', 'exit_code', 'package', 'instance_id', 'repo', 'repos', 'action', 'reason', 'deployer', 'capability'):
            output.append(f"    {k}: Any = None")
        else:
            output.append(f"    {k}: Any = None")
    output.append("")

with open("lib/steglib/event_types.py", "w") as f:
    f.write("\n".join(output))

