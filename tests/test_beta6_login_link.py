"""Offline structural tests: keep the matching login link visible in reauth."""
import ast
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1] / "custom_components" / "lynkco"

class LoginLinkTests(unittest.TestCase):
    def test_both_redirect_form_paths_include_auth_url_placeholder(self):
        module = ast.parse((BASE / "config_flow.py").read_text(encoding="utf-8"))
        config_class = next(x for x in module.body if isinstance(x, ast.ClassDef) and x.name == "LynkCoConfigFlow")
        for method_name in ("async_step_auth_url", "async_step_paste_redirect"):
            method = next(x for x in config_class.body if isinstance(x, ast.AsyncFunctionDef) and x.name == method_name)
            calls = [x for x in ast.walk(method) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "async_show_form"]
            self.assertTrue(calls)
            for call in calls:
                self.assertIn("description_placeholders", [kw.arg for kw in call.keywords])

    def test_both_languages_show_matching_url_placeholder(self):
        for file_name in ("strings.json", "translations/nl.json"):
            obj = json.loads((BASE / file_name).read_text(encoding="utf-8"))
            self.assertIn("{auth_url}", obj["config"]["step"]["paste_redirect"]["description"])

    def test_reauthentication_updates_existing_entry(self):
        source = (BASE / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("async_update_reload_and_abort(", source)
        self.assertIn("LynkCoAPI.exchange_code(", source)
        self.assertIn("self._code_verifier", source)

if __name__ == "__main__":
    unittest.main()
