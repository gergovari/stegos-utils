with open("lib/steglib/events.py", "r") as f:
    content = f.read()
content = content.replace('        })\n        # Fallback', '        })\n    else:\n        # Fallback')
with open("lib/steglib/events.py", "w") as f:
    f.write(content)
