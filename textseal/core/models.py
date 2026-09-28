from django.db import models


class TextRecord(models.Model):
    """The server-side provenance record for a watermarked text."""

    text_id = models.UUIDField(unique=True, db_index=True)
    content_hash = models.CharField(max_length=64)
    watermark_token = models.CharField(max_length=128)
    model_info = models.CharField(max_length=160, blank=True)
    source_note = models.CharField(max_length=240, blank=True)
    canonical_length = models.PositiveIntegerField()
    blockchain_reference = models.CharField(max_length=180)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class VerificationRecord(models.Model):
    """An audit trail which never stores the submitted text itself."""

    verification_id = models.UUIDField(unique=True, db_index=True)
    text_record = models.ForeignKey(TextRecord, null=True, blank=True, on_delete=models.SET_NULL)
    submitted_hash = models.CharField(max_length=64, blank=True)
    watermark_found = models.BooleanField(default=False)
    result = models.CharField(max_length=32)
    detail = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LedgerBlock(models.Model):
    """A tamper-evident local ledger block used for the academic demonstration.

    It is deliberately named separately from a public blockchain transaction. The
    chain provides a testable local fallback until a Polygon/Ethereum contract ABI,
    wallet policy, and RPC provider are approved by the project team.
    """

    block_index = models.PositiveIntegerField(unique=True, db_index=True)
    text_record = models.OneToOneField(TextRecord, related_name="ledger_block", on_delete=models.CASCADE)
    previous_hash = models.CharField(max_length=64)
    payload_hash = models.CharField(max_length=64)
    block_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["block_index"]
