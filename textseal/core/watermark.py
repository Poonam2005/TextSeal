"""Canonicalization, zero-width watermarking, and integrity primitives.

The watermark is deliberately separated from persistence and HTTP code. It carries
only a record identifier and HMAC signature, never the text or secret itself.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass


ZERO = "\u200b"  # zero-width space
ONE = "\u200c"  # zero-width non-joiner
MARKER = "\u2060\u2060"  # word joiner pair
END_MARKER = "\u2060\u200d"  # word joiner + zero-width joiner
ZERO_WIDTH_RE = re.compile(f"[{ZERO}{ONE}\u200d\u2060\ufeff]")


class WatermarkError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedWatermark:
    text_id: uuid.UUID
    token: str
    visible_text: str


def canonicalize(text: str) -> str:
    """Normalize a visible text representation before hashing."""
    if not isinstance(text, str):
        raise WatermarkError("Text must be a string.")
    visible = ZERO_WIDTH_RE.sub("", text)
    normalized = unicodedata.normalize("NFC", visible).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    return normalized.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(canonicalize(text).encode("utf-8")).hexdigest()


def _secret() -> bytes:
    # Local fallback supports a quick demo only. Deployment must use an environment secret.
    return os.environ.get("TEXTSEAL_WATERMARK_SECRET", "dev-watermark-secret-change-me").encode("utf-8")


def make_token(text_id: uuid.UUID) -> str:
    signature = hmac.new(_secret(), text_id.bytes, hashlib.sha256).digest()[:12]
    return base64.b32encode(signature).decode("ascii").rstrip("=")


def valid_token(text_id: uuid.UUID, token: str) -> bool:
    return hmac.compare_digest(make_token(text_id), token)


def _bits(value: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in value)


def _from_bits(bits: str) -> bytes:
    if len(bits) % 8:
        raise WatermarkError("Watermark payload is malformed.")
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def embed(text: str, text_id: uuid.UUID | None = None) -> tuple[str, uuid.UUID, str]:
    visible_text = canonicalize(text)
    if not visible_text:
        raise WatermarkError("Enter some text before watermarking.")
    text_id = text_id or uuid.uuid4()
    token = make_token(text_id)
    payload = f"TS1|{text_id.hex}|{token}".encode("ascii")
    encoded = "".join(ONE if bit == "1" else ZERO for bit in _bits(payload))
    return f"{visible_text}{MARKER}{encoded}{END_MARKER}", text_id, token


def extract(text: str) -> ExtractedWatermark | None:
    start = text.rfind(MARKER)
    if start < 0:
        return None
    payload_start = start + len(MARKER)
    end = text.find(END_MARKER, payload_start)
    if end < 0:
        raise WatermarkError("An incomplete hidden watermark was found.")
    encoded = text[payload_start:end]
    if not encoded or any(char not in {ZERO, ONE} for char in encoded):
        raise WatermarkError("The hidden watermark is malformed.")
    bits = "".join("1" if char == ONE else "0" for char in encoded)
    try:
        prefix, identifier, token = _from_bits(bits).decode("ascii").split("|", 2)
        if prefix != "TS1":
            raise ValueError
        text_id = uuid.UUID(hex=identifier)
    except (UnicodeDecodeError, ValueError) as exc:
        raise WatermarkError("The hidden watermark cannot be decoded.") from exc
    visible_text = text[:start] + text[end + len(END_MARKER):]
    return ExtractedWatermark(text_id=text_id, token=token, visible_text=visible_text)
