with open("tests/test_backend.py", "r") as f:
    content = f.read()

# Replace backend.execute("logs") with backend.execute("unknown") in the error tests
content = content.replace('backend.execute("logs")', 'backend.execute("unknown")')
content = content.replace('backend.execute("logs", follow=True)', 'backend.execute("logs", follow=True)') # Make sure this wasn't broken

with open("tests/test_backend.py", "w") as f:
    f.write(content)
