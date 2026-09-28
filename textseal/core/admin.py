from django.contrib import admin

from .models import LedgerBlock, TextRecord, VerificationRecord


@admin.register(TextRecord)
class TextRecordAdmin(admin.ModelAdmin):
    list_display = ("text_id", "model_info", "canonical_length", "created_at")
    search_fields = ("text_id", "content_hash", "model_info")


@admin.register(VerificationRecord)
class VerificationRecordAdmin(admin.ModelAdmin):
    list_display = ("verification_id", "result", "watermark_found", "created_at")
    list_filter = ("result", "watermark_found")


@admin.register(LedgerBlock)
class LedgerBlockAdmin(admin.ModelAdmin):
    list_display = ("block_index", "text_record", "block_hash", "created_at")
    search_fields = ("text_record__text_id", "block_hash", "payload_hash")
