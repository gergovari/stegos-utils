import re
with open("tests/test_daemon_api.py", "r") as f:
    content = f.read()

replacement = """    @patch("steglib.daemon_api.LifecycleManager")
    def test_lifecycle_controller_restart(mock_lm, dispatcher):
        args = {"ctl_action": "restart", "package": "pkg1"}
        
        def fake_execute(action, pkg, *args, **kwargs):
            if action == "status":
                return {"pkg1": {"state": "running"}}
            return None
        mock_lm.return_value.execute.side_effect = fake_execute
        
        dispatcher.dispatch("ctl.execute", args, None, None)
        mock_lm.return_value.execute.assert_any_call("stop", ["pkg1"], False, follow=False)
        mock_lm.return_value.execute.assert_any_call("start", ["pkg1"], False, follow=False)
"""

content = re.sub(r'    @patch\("steglib\.daemon_api\.LifecycleManager"\)\n    def test_lifecycle_controller_restart\(mock_lm, dispatcher\):.*?mock_lm\.return_value\.execute\.assert_any_call\("start".*?\n', replacement, content, flags=re.DOTALL)

with open("tests/test_daemon_api.py", "w") as f:
    f.write(content)
