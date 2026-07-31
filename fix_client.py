with open("lib/steglib/client.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith("class StegClient:"):
        idx = i
        break

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
lines.insert(idx, finalize_str)

with open("lib/steglib/client.py", "w") as f:
    f.writelines(lines)
