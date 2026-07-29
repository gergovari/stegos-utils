import subprocess
import time
import os
with open("test_a.log", "a") as f:
    subprocess.Popen(["echo", "hello world 2"], stdout=f, stderr=f, preexec_fn=os.setsid)
time.sleep(1)
with open("test_a.log", "r") as f:
    print("LOG:", f.read())
