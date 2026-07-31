import os

# 1. Fix test_lifecycle.py fake_execute signature
f = "tests/test_lifecycle.py"
with open(f, "r") as fd:
    content = fd.read()
content = content.replace("def fake_execute(self, action, if_created, follow=False):", "def fake_execute(self, action, if_created, follow=False, tails=\"all\"):")
with open(f, "w") as fd:
    fd.write(content)

# 2. Fix test_daemon_api.py assertions
f = "tests/test_daemon_api.py"
with open(f, "r") as fd:
    content = fd.read()
content = content.replace("follow=False)", "follow=False, tails=\"all\")")
content = content.replace("follow=True)", "follow=True, tails=\"all\")")
with open(f, "w") as fd:
    fd.write(content)

