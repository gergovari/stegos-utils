import os

files = ["bin/stegpkg", "bin/stegctl", "bin/steggroup"]

for fpath in files:
    if os.path.exists(fpath):
        with open(fpath, "r") as f:
            content = f.read()
        
        bad_str = 'console.print(f"[bold red]✖[/bold red] [white]{e}\nDetails:\n{e.details}[/white]")'
        good_str = 'console.print(f"[bold red]✖[/bold red] [white]{e}\\nDetails:\\n{e.details}[/white]")'
        
        content = content.replace(bad_str, good_str)
        
        with open(fpath, "w") as f:
            f.write(content)
