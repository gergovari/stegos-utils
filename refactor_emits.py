import os
import re

def to_class_name(event_name):
    return "".join(x.capitalize() for x in event_name.split("_")) + "Event"

def process_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    # Find all events.emit("...", ...) calls
    # We use a robust regex that handles multiline if they aren't too crazy, 
    # but let's assume they are mostly on one line or simple multiline.
    # Actually, ast parsing is safer, but re can work if we are careful.
    
    # A safer regex for events.emit("event_name", kwargs)
    # We will find `events.emit("event_name"` and then parse to the matching parenthesis.
    
    # Let's just use re.sub with a function.
    pattern = r'events\.emit\(\s*["\']([a-zA-Z0-9_]+)["\']\s*(.*?)\)'
    
    imports_needed = set()
    
    def repl(m):
        event_name = m.group(1)
        args = m.group(2)
        
        class_name = to_class_name(event_name)
        imports_needed.add(class_name)
        
        if args.startswith(","):
            args = args[1:].strip()
            
        if args:
            return f"events.emit({class_name}({args}))"
        else:
            return f"events.emit({class_name}())"

    new_content, count = re.subn(pattern, repl, content, flags=re.DOTALL)
    
    if count > 0:
        # Add imports
        import_stmt = f"from steglib.event_types import {', '.join(sorted(imports_needed))}"
        
        # Insert after imports
        lines = new_content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                pass
            elif line.strip() == "":
                pass
            else:
                lines.insert(i, import_stmt)
                break
        
        with open(filepath, "w") as f:
            f.write("\n".join(lines))
        print(f"Updated {filepath} with {count} replacements.")

for root, _, files in os.walk("lib/steglib"):
    for file in files:
        if file.endswith(".py") and file != "events.py" and file != "event_types.py":
            process_file(os.path.join(root, file))
