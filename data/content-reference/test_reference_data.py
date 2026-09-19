"""Focused contract tests for the sanitized reference pack."""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prepare_content_reference", ROOT / "scripts" / "prepare-content-reference.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReferenceDataTests(unittest.TestCase):
    def test_repaired_rows_and_quarantine(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            manifest = module.prepare(output=out)
            self.assertEqual(manifest["repaired_row_widths"], {
                "category_taxonomy.csv": 1,
                "source_fetch_policies.csv": 5,
                "first_party_monitors.csv": 2,
            })
            self.assertEqual(module.checked_prepared(out), manifest)
            expected = {
                "categories.csv": 6, "workflow_status.csv": 1,
                "action_suggestions.csv": 21, "fetch_policies_advisory.csv": 8,
                "monitors_advisory.csv": 10, "entity_candidates.csv": 53,
                "entity_quarantine.csv": 14,
            }
            for file, count in expected.items():
                with (out / file).open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), count, file)
                self.assertTrue(all(None not in row for row in rows), file)
                if file == "entity_candidates.csv":
                    self.assertFalse(module.QUARANTINED.intersection(
                        row["canonical_name"] for row in rows
                    ))
                    self.assertTrue(all(not row["approved_aliases"] for row in rows))
                if file == "entity_quarantine.csv":
                    self.assertEqual({row["canonical_name"] for row in rows}, module.QUARANTINED)
            seeds = module.prepared_seeds(out / "disabled_feed_seeds.json")
            self.assertTrue(all(seed["enabled"] is False for seed in seeds))
            (out / "disabled_feed_seeds.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                module.checked_prepared(out)

    def test_api_origin_and_redirect_guard(self):
        self.assertEqual(module.api_origin("http://127.0.0.1:8000"), "http://127.0.0.1:8000")
        self.assertEqual(module.api_origin("http://[::1]:8000"), "http://[::1]:8000")
        self.assertEqual(module.api_origin("https://radar.example"), "https://radar.example")
        for unsafe in ("http://192.168.1.3:5173", "http://example.com",
                       "https://user:secret@example.com", "https://example.com/other"):
            with self.assertRaises(ValueError):
                module.api_origin(unsafe)
        self.assertIsNone(module.RejectRedirects().redirect_request(
            None, None, 302, "redirect", {}, "https://elsewhere.example"
        ))

    def test_unsafe_official_url_is_reported_as_deferred(self):
        class UnsafeSourceOpener:
            def open(self, req, timeout):
                if req.full_url.endswith("/session"):
                    return io.BytesIO(b'{"csrf_token":"test"}')
                if req.get_method() == "GET":
                    return io.BytesIO(json.dumps({"items": [{
                        "name": "Hugging Face",
                        "feed_url": "https://huggingface.co/blog/feed.xml",
                    }]}).encode())
                self.payload = json.loads(req.data)
                body = json.dumps({"detail": {
                    "code": "SOURCE_URL_UNSAFE",
                    "message": "URL resolves to a non-public address",
                }}).encode()
                raise HTTPError(req.full_url, 422, "unsafe", {}, io.BytesIO(body))

        opener = UnsafeSourceOpener()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            module.prepare(output=out)
            with patch.object(module, "build_opener", return_value=opener):
                counts = module.apply_seeds(
                    "http://localhost:8000", "dummy-token", out / "disabled_feed_seeds.json"
                )
        self.assertEqual(counts, {
            "existing": 1, "created_disabled": 0, "deferred_unsafe": 1,
        })
        self.assertEqual(opener.payload, {
            "name": "Groq Official Changelog",
            "feed_url": "https://github.com/groq/groq-changelog/commits/main.atom",
            "channel_type": "rss",
        })

    def test_apply_does_not_follow_redirect(self):
        class RedirectingOpener:
            calls = []
            def open(self, req, timeout):
                self.calls.append(req.full_url)
                raise HTTPError(req.full_url, 302, "redirect", {"Location": "https://elsewhere.example"}, None)

        opener = RedirectingOpener()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            module.prepare(output=out)
            with patch.object(module, "build_opener", return_value=opener):
                with self.assertRaises(HTTPError):
                    module.apply_seeds("http://localhost:8000", "dummy-token", out / "disabled_feed_seeds.json")
            self.assertEqual(opener.calls, ["http://localhost:8000/api/v1/admin/session"])


if __name__ == "__main__":
    unittest.main()
