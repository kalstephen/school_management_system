from django.conf import settings
from django.db import models

from apps.core.models import School


class SyncOp(models.Model):
    """One change made offline on a teacher's phone. op_id is generated on the phone,
    so sending the same change twice never applies it twice."""

    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        CONFLICT = "conflict", "Conflict — someone changed it since"
        REJECTED = "rejected", "Rejected"
        RESOLVED = "resolved", "Conflict resolved"

    op_id = models.UUIDField(unique=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20)
    payload = models.JSONField()
    base_version = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices)
    detail = models.CharField(max_length=300, blank=True)
    server_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
