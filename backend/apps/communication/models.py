from django.conf import settings
from django.db import models

from apps.core.models import SchoolOwned
from apps.schoolsetup.models import SchoolClass


class Notice(SchoolOwned):
    class Audience(models.TextChoices):
        ALL_STAFF = "all_staff", "All staff"
        TEACHERS = "teachers", "Teaching staff"
        ROLES = "roles", "Selected roles"

    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.ALL_STAFF)
    roles = models.JSONField(default=list, blank=True, help_text="Role keys when audience is 'roles'")
    pinned = models.BooleanField(default=False)
    expires_on = models.DateField(null=True, blank=True)
    attachment = models.FileField(upload_to="notices/", blank=True)
    email_guardians = models.BooleanField(default=False, help_text="Also email guardians (as a circular)")
    guardian_classes = models.ManyToManyField(
        SchoolClass, blank=True, help_text="Empty: guardians of every class"
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-pinned", "-created_at"]

    def __str__(self):
        return self.title


class Notification(SchoolOwned):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    link = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class EmailLog(SchoolOwned):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    to = models.EmailField()
    subject = models.CharField(max_length=200)
    kind = models.CharField(max_length=30, help_text="notice, report_card, ...")
    status = models.CharField(max_length=10, choices=Status.choices)
    error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
