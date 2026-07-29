import subprocess
import time
with open("test.log", "w") as f:
    subprocess.Popen(["echo", "hello world"], stdout=f, stderr=f)
time.sleep(1)
with open("test.log", "r") as f:
    print("LOG:", f.read())
