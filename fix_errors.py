import os
import re

files = ["bin/stegpkg", "bin/stegctl", "bin/steggroup"]

new_exception_block = """    except Exception as e:
        from rich.console import Console
        console = Console(stderr=True)
        if getattr(e, 'details', None):
            if args.verbose:
                console.print(f"[bold red]✖[/bold red] [white]{e}\\nDetails:\\n{e.details}[/white]")
            else:
                console.print(f"[bold red]✖[/bold red] [white]{e} (run with --verbose for logs)[/white]")
        else:
            console.print(f"[bold red]✖[/bold red] [white]{e}[/white]")
        sys.exit(1)"""

for fpath in files:
    if os.path.exists(fpath):
        with open(fpath, "r") as f:
            content = f.read()
        
        # Regex to replace the except block
        content = re.sub(r'    except Exception as e:\n        if getattr\(e, \'details\', None\):\n.*?\n        sys\.exit\(1\)', new_exception_block, content, flags=re.DOTALL)
        
        with open(fpath, "w") as f:
            f.write(content)
