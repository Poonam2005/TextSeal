import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from django.core.files.uploadedfile import SimpleUploadedFile
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

    def test_docx_upload_is_extracted_and_registered(self):
        document = Document()
        document.add_paragraph("A readable DOCX sample.")
        content = BytesIO()
        document.save(content)
        upload = SimpleUploadedFile("sample.docx", content.getvalue())
        response = self.client.post("/api/watermark", {"file": upload})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["provenance"]["content_hash"], content_hash("A readable DOCX sample."))

    def test_utf8_text_upload_remains_supported(self):
        upload = SimpleUploadedFile("sample.txt", "UTF-8 café sample.".encode("utf-8"))
        response = self.client.post("/api/watermark", {"file": upload})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["provenance"]["content_hash"], content_hash("UTF-8 café sample."))

    @patch("textseal.core.views.PdfReader")
    def test_pdf_upload_is_extracted_and_registered(self, pdf_reader):
        pdf_reader.return_value = SimpleNamespace(
            is_encrypted=False,
            pages=[SimpleNamespace(extract_text=lambda: "A readable PDF sample.")],
        )
        upload = SimpleUploadedFile("sample.pdf", b"%PDF-1.4 test")
        response = self.client.post("/api/watermark", {"file": upload})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["provenance"]["content_hash"], content_hash("A readable PDF sample."))

    def test_unsupported_and_unreadable_uploads_return_clear_errors(self):
        unsupported = SimpleUploadedFile("sample.rtf", b"text")
        response = self.client.post("/api/verify", {"file": unsupported})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Supported uploads", response.json()["error"])

        unreadable = SimpleUploadedFile("sample.pdf", b"not a PDF")
        response = self.client.post("/api/verify", {"file": unreadable})
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid or unreadable", response.json()["error"])

        oversized = SimpleUploadedFile("large.txt", b"x" * 1_000_001)
        response = self.client.post("/api/verify", {"file": oversized})
        self.assertEqual(response.status_code, 400)
        self.assertIn("1 MB or smaller", response.json()["error"])

    @patch("textseal.core.views.PdfReader")
    def test_empty_pdf_extraction_returns_clear_error(self, pdf_reader):
        pdf_reader.return_value = SimpleNamespace(
            is_encrypted=False,
            pages=[SimpleNamespace(extract_text=lambda: " ")],
        )
        upload = SimpleUploadedFile("empty.pdf", b"%PDF-1.4 test")
        response = self.client.post("/api/watermark", {"file": upload})
        self.assertEqual(response.status_code, 400)
        self.assertIn("No readable text", response.json()["error"])

    def test_robustness_evaluation_reports_cases_without_audit_writes(self):
        registration = self.register()
        response = self.client.post("/api/evaluate", {"text": registration["watermarked_text"]})
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["passed"], 4)
        self.assertEqual(data["total"], 4)
        self.assertEqual(VerificationRecord.objects.count(), 0)
        self.assertEqual([case["actual"] for case in data["cases"]], ["authentic", "authentic", "modified", "not_registered"])

    def test_evaluation_requires_a_registered_watermark(self):
        response = self.client.post("/api/evaluate", {"text": "plain text"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid registered", response.json()["error"])

    def test_receipt_shows_proof_without_sensitive_metadata_or_text(self):
        registration = self.client.post("/api/watermark", {
            "text": self.original, "source_note": "private source note", "model_info": "private model info",
        }).json()
        response = self.client.get(registration["receipt_url"])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, registration["provenance"]["content_hash"])
        self.assertNotContains(response, self.original)
        self.assertNotContains(response, "private source note")
        self.assertNotContains(response, "private model info")
        self.assertNotContains(response, registration["watermarked_text"])

    def test_receipt_returns_not_found_for_unknown_identifier(self):
        response = self.client.get("/receipt/00000000-0000-0000-0000-000000000000")
        self.assertEqual(response.status_code, 404)
