from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/health", views.health, name="health"),
    path("api/watermark", views.watermark_text, name="watermark"),
    path("api/verify", views.verify_text, name="verify"),
    path("api/evaluate", views.evaluate_robustness, name="evaluate"),
    path("api/provenance/<uuid:text_id>", views.provenance, name="provenance"),
    path("receipt/<uuid:text_id>", views.receipt, name="receipt"),
    path("api/history", views.history, name="history"),
]
