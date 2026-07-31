import re
import os
import glob

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Fix double commas and dangling commas
    content = re.sub(r',\s*,', ',', content)
    content = re.sub(r'\(\s*,', '(', content)
    # Fix backend.py regex error
    content = content.replace(r"line=line.rstrip(\'\n\')", r"line=line.rstrip('\n')")
    
    with open(filepath, 'w') as f:
        f.write(content)

for py_file in glob.glob("lib/steglib/*.py"):
    fix_file(py_file)
