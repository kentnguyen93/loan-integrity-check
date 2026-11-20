"""Security regression tests for the generated, self-contained demo."""
import base64, hashlib, json, os, re, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from build_demo import ROOT, html_json


class DemoSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "demo", "index.html"), encoding="utf-8") as f:
            cls.html = f.read()

    def test_embedded_json_cannot_close_the_script_element(self):
        original = "</script><script>alert('xss')</script>&\u2028\u2029"
        payload = html_json({"payload": original})
        self.assertNotIn("<", payload)
        self.assertNotIn(">", payload)
        self.assertNotIn("&", payload)
        self.assertNotIn("\u2028", payload)
        self.assertNotIn("\u2029", payload)
        self.assertEqual(json.loads(payload), {"payload": original})

    def test_csp_matches_the_exact_inline_script_and_blocks_connections(self):
        script = self.html.split("<script>", 1)[1].split("</script>", 1)[0]
        digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
        match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', self.html)
        self.assertIsNotNone(match)
        policy = match.group(1)
        self.assertIn("default-src 'none'", policy)
        self.assertIn("script-src 'sha256-" + digest + "'", policy)
        self.assertNotIn("script-src 'unsafe-inline'", policy)
        self.assertIn("connect-src 'none'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertNotIn("/*CSP_HASH*/", self.html)

    def test_demo_has_no_external_resources_or_persistent_storage(self):
        self.assertIsNone(re.search(r"(?i)<(?:script|img|iframe|audio|video|source)\b[^>]*\bsrc\s*=", self.html))
        self.assertIsNone(re.search(r"(?i)<link\b[^>]*\bhref\s*=", self.html))
        self.assertNotIn("localStorage", self.html)
        self.assertNotIn("sessionStorage", self.html)
        self.assertNotIn("indexedDB", self.html)
        self.assertNotIn("document.cookie", self.html)
        self.assertNotRegex(self.html, r"\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(")


if __name__ == "__main__":
    unittest.main()
