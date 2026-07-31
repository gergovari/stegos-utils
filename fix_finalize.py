import re

with open("lib/steglib/client.py", "r") as f:
    content = f.read()

# Remove the incorrectly placed finalize
content = re.sub(r'\n    def finalize\(self\):.*?\n            self\._list_buffer = \[\]\n', '', content, flags=re.DOTALL)

# Find the end of EventFormatter. It ends with:
#         if self.verbose:
#             self.console.print(f"[dim]Event: {event_type} {getattr(event, '_raw_data', event.to_dict())}[/dim]")

finalize_str = """
    def finalize(self):
        \"\"\"Called when the stream ends to print any buffered data.\"\"\"
        if self._list_buffer and self.console:
            from rich.table import Table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Instance", style="dim", width=25)
            table.add_column("App", width=25)
            for item in self._list_buffer:
                table.add_row(getattr(item, 'instance_id', '') or "", getattr(item, 'package', '') or "")
            self.console.print(table)
            self._list_buffer = []
"""

target = "        if self.verbose:\n            self.console.print(f\"[dim]Event: {event_type} {getattr(event, '_raw_data', event.to_dict())}[/dim]\")\n"

if target in content:
    content = content.replace(target, target + "\n" + finalize_str)
else:
    print("Target not found!")

with open("lib/steglib/client.py", "w") as f:
    f.write(content)
