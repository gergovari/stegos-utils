import re
import os

def process_file(filepath, replacements):
    if not os.path.exists(filepath): return
    with open(filepath, 'r') as f:
        content = f.read()

    content = re.sub(r'import logging\n', 'from steglib import events\n', content)
    content = re.sub(r'logger = logging\.getLogger\(__name__\)\n', '', content)
    
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)
        
    with open(filepath, 'w') as f:
        f.write(content)

dockerd_repl = [
    (r'logger\.info\("Stopping orphaned isolated dockerd\.\.\."\)', r'events.emit("dockerd_stopping_orphaned")'),
    (r'logger\.info\("Starting isolated dockerd\.\.\."\)', r'events.emit("dockerd_starting")'),
    (r'logger\.info\("Waiting for isolated dockerd to be ready\.\.\."\)', r'events.emit("dockerd_waiting_ready")')
]

server_repl = [
    (r'logger\.info\("Handling connection\.\.\."\)', r'events.emit("server_handling_connection")'),
    (r'logger\.error\("Error accepting connection: %s", e\)', r'events.emit("server_accept_error", error=str(e))'),
    (r'logger\.error\("Handler error: %s", e\)', r'events.emit("server_handler_error", error=str(e))')
]

utils_repl = [
    (r'logger\.info\(f"Running: \{\' \'\.join\(cmd\)\}"\)', r'events.emit("utils_running_command", command=" ".join(cmd))'),
    (r'logger\.error\(err_msg\)', r'events.emit("utils_command_failed", error=err_msg)'),
    (r'logger\.error\("Command stderr: %s", process\.stderr\.strip\(\)\)', r'events.emit("utils_command_stderr", stderr=process.stderr.strip())')
]

injectors_repl = [
    (r'logger\.warning\(\n                "No matching target services found for injection "\n                "\(target_services=%s, available=%s\)\.",\n                target_services,\n                list\(services\.keys\(\)\),\n            \)', r'events.emit("injector_no_target_services", targets=target_services, available=list(services.keys()))')
]

process_file('lib/steglib/dockerd.py', dockerd_repl)
process_file('lib/steglib/server.py', server_repl)
process_file('lib/steglib/utils.py', utils_repl)
process_file('lib/steglib/injectors.py', injectors_repl)
