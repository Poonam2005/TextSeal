import os

from django.test import TestCase

from .models import LedgerBlock, TextRecord, VerificationRecord
from .watermark import canonicalize, content_hash, embed, extract


class WatermarkPrimitiveTests(TestCase):
    def setUp(self):
        os.environ["TEXTSEAL_WATERMARK_SECRET"] = "test-secret"

    def test_embed_extract_and_hash_round_trip(self):
        original = "A small\r\ntext with a trailing space.   "
        watermarked, text_id, token = embed(original)
        found = extract(watermarked)
        self.assertEqual(found.text_id, text_id)
        self.assertEqual(found.token, token)
        self.assertEqual(canonicalize(found.visible_text), canonicalize(original))
        self.assertEqual(content_hash(watermarked), content_hash(original))


class ApiTests(TestCase):
    def setUp(self):
        os.environ["TEXTSEAL_WATERMARK_SECRET"] = "test-secret"
        self.original = "TextSeal records provenance without changing visible text."

    def register(self):
        response = self.client.post("/api/watermark", {"text": self.original, "model_info": "Test model"})
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_registration_creates_provenance_record(self):
        data = self.register()
        self.assertEqual(data["status"], "registered")
        self.assertEqual(TextRecord.objects.count(), 1)
        self.assertEqual(LedgerBlock.objects.count(), 1)
        self.assertTrue(data["provenance"]["ledger_status"])
        self.assertEqual(data["provenance"]["content_hash"], content_hash(self.original))

    def test_exact_registered_text_is_authentic(self):
        registration = self.register()
        response = self.client.post("/api/verify", {"text": registration["watermarked_text"]})
        result = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result["result"], "authentic")
        self.assertTrue(result["hash_matches"])

    def test_visible_change_is_modified(self):
        registration = self.register()
        changed = registration["watermarked_text"].replace("records", "stores")
        response = self.client.post("/api/verify", {"text": changed})
        result = response.json()
        self.assertEqual(result["result"], "modified")
        self.assertTrue(result["watermark_found"])
        self.assertFalse(result["hash_matches"])

    def test_unmarked_text_is_not_registered(self):
        response = self.client.post("/api/verify", {"text": "An unrelated sample."})
        result = response.json()
        self.assertEqual(result["result"], "not_registered")
        self.assertFalse(result["watermark_found"])
        self.assertEqual(VerificationRecord.objects.count(), 1)

    def test_damaged_ledger_never_returns_authentic(self):
        registration = self.register()
        block = TextRecord.objects.get().ledger_block
        block.previous_hash = "0" * 64
        block.save(update_fields=["previous_hash"])
        response = self.client.post("/api/verify", {"text": registration["watermarked_text"]})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["result"], "verification_unavailable")

    def test_history_shows_project_review_evidence(self):
        registration = self.register()
        self.client.post("/api/verify", {"text": registration["watermarked_text"]})
        response = self.client.get("/api/history")
        data = response.json()
        self.assertTrue(data["ledger_integrity"])
        self.assertEqual(data["registered_count"], 1)
        self.assertEqual(data["verification_count"], 1)
        self.assertEqual(len(data["records"]), 1)
