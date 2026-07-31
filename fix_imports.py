import os
import re

for root, _, files in os.walk("lib/steglib"):
    for file in files:
        if file.endswith(".py") and file not in ["events.py", "event_types.py", "__init__.py"]:
            filepath = os.path.join(root, file)
            with open(filepath, "r") as f:
                content = f.read()
            
            # replace all `from steglib.event_types import ...` with `from steglib.event_types import *`
            content = re.sub(r'from steglib\.event_types import[^\n]*\n(?:    [^\n]*\n)*', 'from steglib.event_types import *\n', content)
            
            # Sometimes it might be on multiple lines like ( \n ... \n )
            content = re.sub(r'from steglib\.event_types import \([^)]+\)', 'from steglib.event_types import *', content)
            
            with open(filepath, "w") as f:
                f.write(content)

