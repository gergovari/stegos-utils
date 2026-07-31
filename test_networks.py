import json, subprocess
res = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True)
if res.stdout:
    cid = res.stdout.splitlines()[0]
    res2 = subprocess.run(["docker", "inspect", cid], capture_output=True, text=True)
    data = json.loads(res2.stdout)
    print("Networks keys:")
    print(list(data[0]["NetworkSettings"]["Networks"].keys()))
