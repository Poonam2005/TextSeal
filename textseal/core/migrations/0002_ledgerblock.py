# Adds the explicit local tamper-evident ledger used in the final-year prototype.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="LedgerBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("block_index", models.PositiveIntegerField(db_index=True, unique=True)),
                ("previous_hash", models.CharField(max_length=64)),
                ("payload_hash", models.CharField(max_length=64)),
                ("block_hash", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("text_record", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_block", to="core.textrecord")),
            ],
            options={"ordering": ["block_index"]},
        ),
    ]
