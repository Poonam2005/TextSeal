"""Tamper-evident provenance ledger.

This is a transparent local fallback for the final-year project demonstration.
It does not claim to be an Ethereum/Polygon transaction. A production adapter
can call a smart contract from this boundary once its ABI is finalized.
"""
from __future__ import annotations

import hashlib

from django.db import transaction

from .models import LedgerBlock, TextRecord

GENESIS_HASH = hashlib.sha256(b"TextSeal local ledger genesis v1").hexdigest()


class LedgerError(RuntimeError):
    """Raised when a provenance record cannot receive a valid ledger entry."""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_hash(record: TextRecord) -> str:
    return _sha256(f"{record.text_id}|{record.content_hash}|{record.watermark_token}")


def _block_hash(index: int, previous_hash: str, payload_hash: str) -> str:
    return _sha256(f"{index}|{previous_hash}|{payload_hash}")


def append_block(record: TextRecord) -> LedgerBlock:
    """Append one record to the local chain and return its immutable reference."""
    with transaction.atomic():
        if hasattr(record, "ledger_block"):
            return record.ledger_block
        previous = LedgerBlock.objects.select_for_update().order_by("-block_index").first()
        block_index = previous.block_index + 1 if previous else 1
        previous_hash = previous.block_hash if previous else GENESIS_HASH
        payload_hash = _payload_hash(record)
        block_hash = _block_hash(block_index, previous_hash, payload_hash)
        block = LedgerBlock.objects.create(
            block_index=block_index,
            text_record=record,
            previous_hash=previous_hash,
            payload_hash=payload_hash,
            block_hash=block_hash,
        )
        record.blockchain_reference = f"local-ledger://block/{block_index}/{block_hash[:16]}"
        record.save(update_fields=["blockchain_reference"])
        return block


def validate_chain() -> bool:
    """Verify every link in the ledger. A mismatch is never treated as authentic."""
    expected_previous = GENESIS_HASH
    expected_index = 1
    for block in LedgerBlock.objects.select_related("text_record").order_by("block_index"):
        if block.block_index != expected_index or block.previous_hash != expected_previous:
            return False
        if block.payload_hash != _payload_hash(block.text_record):
            return False
        if block.block_hash != _block_hash(block.block_index, block.previous_hash, block.payload_hash):
            return False
        expected_previous = block.block_hash
        expected_index += 1
    return True


def record_is_in_valid_chain(record: TextRecord) -> bool:
    """Check that the record has a block and that the full chain is sound."""
    try:
        block = record.ledger_block
    except LedgerBlock.DoesNotExist:
        return False
    return block.payload_hash == _payload_hash(record) and validate_chain()
