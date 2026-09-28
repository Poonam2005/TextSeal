import json
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .ledger import LedgerError, append_block, record_is_in_valid_chain, validate_chain
from .models import LedgerBlock, TextRecord, VerificationRecord
from .watermark import WatermarkError, canonicalize, content_hash, embed, extract, valid_token


def index(request):
    return render(request, "core/index.html")


def _payload(request):
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError as exc:
            raise WatermarkError("Request body must contain valid JSON.") from exc
    return request.POST


def _text_from_request(request, data):
    uploaded = request.FILES.get("file")
    text = data.get("text", "")
    if uploaded:
        if uploaded.size > settings.MAX_UPLOAD_SIZE:
            raise WatermarkError("Uploads must be 1 MB or smaller.")
        if Path(uploaded.name).suffix.lower() not in {".txt", ".md"}:
            raise WatermarkError("Only .txt and .md files are supported.")
        try:
            text = uploaded.read().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WatermarkError("Uploaded files must be UTF-8 encoded.") from exc
    if not isinstance(text, str):
        raise WatermarkError("Text must be a string.")
    if len(text) > 100_000:
        raise WatermarkError("Text is limited to 100,000 characters.")
    return text


def _provenance_data(record):
    try:
        block = record.ledger_block
        ledger_status = record_is_in_valid_chain(record)
        block_number = block.block_index
    except LedgerBlock.DoesNotExist:
        ledger_status = False
        block_number = None
    return {
        "text_id": str(record.text_id),
        "content_hash": record.content_hash,
        "model_info": record.model_info or "Not provided",
        "source_note": record.source_note or "Not provided",
        "canonical_length": record.canonical_length,
        "blockchain_reference": record.blockchain_reference,
        "ledger_status": ledger_status,
        "block_number": block_number,
        "created_at": record.created_at.isoformat(),
    }


@require_GET
def health(request):
    return JsonResponse({
        "status": "ok",
        "blockchain_mode": os.environ.get("BLOCKCHAIN_MODE", "local-tamper-evident-ledger"),
        "ledger_integrity": validate_chain(),
    })


@require_POST
def watermark_text(request):
    try:
        data = _payload(request)
        original = _text_from_request(request, data)
        watermarked_text, text_id, token = embed(original)
        cleaned = canonicalize(original)
        with transaction.atomic():
            record = TextRecord.objects.create(
                text_id=text_id,
                content_hash=content_hash(cleaned),
                watermark_token=token,
                model_info=str(data.get("model_info", "")).strip()[:160],
                source_note=str(data.get("source_note", "")).strip()[:240],
                canonical_length=len(cleaned),
                blockchain_reference="pending",
            )
            append_block(record)
        return JsonResponse({
            "status": "registered",
            "message": "Watermark embedded and provenance added to the tamper-evident local ledger.",
            "watermarked_text": watermarked_text,
            "provenance": _provenance_data(record),
            "watermark_note": "The watermark is invisible. Keep this exact output for later verification.",
        }, status=201)
    except (WatermarkError, LedgerError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


def _audit(record, submitted_hash, found, result, detail):
    VerificationRecord.objects.create(
        verification_id=uuid.uuid4(), text_record=record, submitted_hash=submitted_hash,
        watermark_found=found, result=result, detail=detail,
    )


@require_POST
def verify_text(request):
    try:
        data = _payload(request)
        submitted = _text_from_request(request, data)
        watermark = extract(submitted)
        submitted_hash = content_hash(submitted)
        if not watermark:
            _audit(None, submitted_hash, False, "not_registered", "No TextSeal watermark was found.")
            return JsonResponse({
                "result": "not_registered", "label": "Not registered", "watermark_found": False,
                "hash_matches": False, "detail": "No TextSeal watermark was found in the submitted text.",
            })
        if not valid_token(watermark.text_id, watermark.token):
            _audit(None, submitted_hash, True, "invalid_watermark", "Watermark signature is invalid.")
            return JsonResponse({
                "result": "invalid_watermark", "label": "Watermark invalid", "watermark_found": True,
                "hash_matches": False, "detail": "A hidden payload was found, but its signature is invalid.",
            })
        record = TextRecord.objects.filter(text_id=watermark.text_id).first()
        if not record:
            _audit(None, submitted_hash, True, "not_registered", "Watermark refers to an unavailable record.")
            return JsonResponse({
                "result": "not_registered", "label": "Not registered", "watermark_found": True,
                "hash_matches": False, "detail": "The watermark is valid but this server has no matching provenance record.",
            })
        if record.watermark_token != watermark.token:
            _audit(record, submitted_hash, True, "invalid_watermark", "Record token mismatch.")
            return JsonResponse({
                "result": "invalid_watermark", "label": "Watermark invalid", "watermark_found": True,
                "hash_matches": False, "detail": "The extracted watermark does not match its registered record.",
                "provenance": _provenance_data(record),
            })
        if not record_is_in_valid_chain(record):
            detail = "The provenance ledger is unavailable or inconsistent. TextSeal will not claim authenticity."
            _audit(record, submitted_hash, True, "verification_unavailable", detail)
            return JsonResponse({
                "result": "verification_unavailable", "label": "Verification unavailable", "watermark_found": True,
                "hash_matches": False, "detail": detail, "provenance": _provenance_data(record),
            }, status=503)
        hash_matches = record.content_hash == submitted_hash
        if hash_matches:
            result, label, detail = "authentic", "Authentic & unchanged", "Watermark, provenance record, and SHA-256 hash all match."
        else:
            result, label, detail = "modified", "Modified / tampered", "A registered watermark was found, but the canonical SHA-256 hash differs."
        _audit(record, submitted_hash, True, result, detail)
        return JsonResponse({
            "result": result, "label": label, "watermark_found": True,
            "hash_matches": hash_matches, "detail": detail, "provenance": _provenance_data(record),
        })
    except WatermarkError as exc:
        _audit(None, "", False, "invalid_input", str(exc))
        return JsonResponse({"error": str(exc)}, status=400)


@require_GET
def provenance(request, text_id):
    return JsonResponse({"provenance": _provenance_data(get_object_or_404(TextRecord, text_id=text_id))})


@require_GET
def history(request):
    """Small, anonymized activity feed for the final review demonstration."""
    records = TextRecord.objects.select_related("ledger_block").all()[:20]
    verifications = VerificationRecord.objects.select_related("text_record").all()[:20]
    return JsonResponse({
        "ledger_integrity": validate_chain(),
        "registered_count": TextRecord.objects.count(),
        "verification_count": VerificationRecord.objects.count(),
        "records": [_provenance_data(record) for record in records],
        "verifications": [{
            "verification_id": str(item.verification_id),
            "text_id": str(item.text_record.text_id) if item.text_record else None,
            "result": item.result,
            "watermark_found": item.watermark_found,
            "created_at": item.created_at.isoformat(),
        } for item in verifications],
    })
