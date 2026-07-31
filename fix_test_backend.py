import re

with open("tests/test_backend.py", "r") as f:
    lines = f.readlines()

out = []
for line in lines:
    if line.startswith("@patch(\"steglib.backend.logger"):
        if "steglib.events.emit" not in "".join(out[-2:]):
            out.append('@patch("steglib.events.emit")\n')
    else:
        out.append(line)

with open("tests/test_backend.py", "w") as f:
    f.writelines(out)
