import sys
sys.path.insert(0, "/home/ubu/Documents/stegos-workspace/stegos-utils/lib")
from steglib.manager import CapabilityManager
cap_manager = CapabilityManager("/home/ubu/Documents/stegos-workspace/stegos-apps-base")
cap_manager.load_capabilities()
providers = cap_manager.get_providers("reverse-proxy")
for pid, info in providers.items():
    print(pid, info["injector"]["docker-compose"]["env"])
