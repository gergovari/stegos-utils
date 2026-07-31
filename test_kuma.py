import yaml
with open("/home/ubu/Documents/stegos-workspace/stegos-apps-base/uptime-kuma/manifest.yml", "r") as f:
    print(yaml.safe_load(f)["capabilities"]["consumes"])
