import re
import glob

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Generic fallback: if we see logger.X(msg, args...), we replace it with events.emit("log_X", ...)
    # This is tricky with regex due to nested parentheses. We'll do a simple loop over lines.
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'logger.' in line:
            # We want to replace logger.info(X) with events.emit("log_info", message=X)
            # Find the method
            match = re.search(r'logger\.(info|warning|error|debug|exception)\((.*)\)', line)
            if match:
                lvl = match.group(1)
                args = match.group(2)
                # Just emit log event
                if '%s' in args and ',' in args and not args.startswith('f"'):
                    # It's an old style formatting logger.info("msg %s", var)
                    # Convert to % formatting roughly
                    # This is just a hack to make it compile
                    parts = args.split(',', 1)
                    if len(parts) == 2:
                        new_args = f'{parts[0]} % ({parts[1]})'
                    else:
                        new_args = args
                else:
                    new_args = args
                    
                lines[i] = line[:match.start()] + f'events.emit("log_{lvl}", message={new_args})' + line[match.end():]

    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))

for py_file in glob.glob("lib/steglib/*.py"):
    process_file(py_file)
