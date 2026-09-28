"""Give records created by the first prototype release a ledger block."""
import hashlib

from django.db import migrations


GENESIS = hashlib.sha256(b"TextSeal local ledger genesis v1").hexdigest()


def sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def backfill_ledger(apps, schema_editor):
    TextRecord = apps.get_model("core", "TextRecord")
    LedgerBlock = apps.get_model("core", "LedgerBlock")
    previous_hash = GENESIS
    for index, record in enumerate(TextRecord.objects.order_by("created_at", "id"), start=1):
        payload_hash = sha256(f"{record.text_id}|{record.content_hash}|{record.watermark_token}")
        block_hash = sha256(f"{index}|{previous_hash}|{payload_hash}")
        LedgerBlock.objects.create(
            block_index=index,
            text_record=record,
            previous_hash=previous_hash,
            payload_hash=payload_hash,
            block_hash=block_hash,
        )
        record.blockchain_reference = f"local-ledger://block/{index}/{block_hash[:16]}"
        record.save(update_fields=["blockchain_reference"])
        previous_hash = block_hash


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("core", "0002_ledgerblock")]

    operations = [migrations.RunPython(backfill_ledger, noop)]
