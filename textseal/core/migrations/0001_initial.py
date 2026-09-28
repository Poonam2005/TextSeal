# Generated manually for the initial TextSeal schema.
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TextRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text_id", models.UUIDField(db_index=True, unique=True)),
                ("content_hash", models.CharField(max_length=64)),
                ("watermark_token", models.CharField(max_length=128)),
                ("model_info", models.CharField(blank=True, max_length=160)),
                ("source_note", models.CharField(blank=True, max_length=240)),
                ("canonical_length", models.PositiveIntegerField()),
                ("blockchain_reference", models.CharField(max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="VerificationRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("verification_id", models.UUIDField(db_index=True, unique=True)),
                ("submitted_hash", models.CharField(blank=True, max_length=64)),
                ("watermark_found", models.BooleanField(default=False)),
                ("result", models.CharField(max_length=32)),
                ("detail", models.CharField(max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("text_record", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.textrecord")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
