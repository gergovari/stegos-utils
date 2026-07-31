import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. replace imports
    content = re.sub(r'import logging\n', 'from steglib import events\n', content)
    content = re.sub(r'logger = logging\.getLogger\(__name__\)\n', '', content)
    
    # 2. replace specific log lines
    replacements = [
        (r'logger\.warning\("Circular dependency detected involving \'%s\'", n\)', r'events.emit("circular_dependency", package=n)'),
        (r'logger\.debug\(f"\[\{pkg\}\] Failed to parse networks for pre-creation: \{e\}"\)', r'events.emit("network_precreate_failed", package=pkg, error=str(e))'),
        (r'logger\.debug\(f"Failed to pre-create networks: \{e\}"\)', r'events.emit("network_precreate_error", error=str(e))'),
        (r'logger\.error\(f"\[\{p\}\] Skipping action \'\{action\}\' because dependencies failed\."\)', r'events.emit("skipping_action", package=p, action=action, reason="dependencies failed")'),
        (r'logger\.warning\("\[%s\] No deployer backend found\. Was it installed with stegpkg\?", pkg\)', r'events.emit("no_deployer_backend", package=pkg)'),
        (r'logger\.warning\("\[%s\] Warning: Unknown deployer \'%s\'", pkg, deployer\)', r'events.emit("unknown_deployer", package=pkg, deployer=deployer)'),
        (r'logger\.error\(f"\[\{pkg\}\] Action \'\{action\}\' failed: \{e\}"\)', r'events.emit("action_failed", package=pkg, action=action, error=str(e))'),
        (r'logger\.warning\("\[%s\] Integration provider \'%s\' for capability \'%s\' is missing!", pkg, p, cap_name\)', r'events.emit("integration_missing", consumer=pkg, capability=cap_name, missing_provider=p)')
    ]
    
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)
        
    with open(filepath, 'w') as f:
        f.write(content)

process_file('lib/steglib/lifecycle.py')
