import re

with open("lib/steglib/client.py", "r") as f:
    content = f.read()

replacement = """        # Backend streams
        if event_type == "dockerd_starting_backend":
            if self.verbose: self.console.print("[dim]  └── ⏳ Starting backend...[/dim]", markup=False)
            return
        if event_type == "backend_loading_cache":
            if self.verbose: self.console.print(f"[dim][{data.get('package', 'unknown')}] Backend is loading cache...[/dim]", markup=False)
            return
        if event_type == "backend_log_line":"""

content = content.replace('        # Backend streams\n        if event_type == "backend_log_line":', replacement)

with open("lib/steglib/client.py", "w") as f:
    f.write(content)
