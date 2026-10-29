from django.conf import settings
from django.db import models

from apps.core.models import School
from apps.core.modules import ALL_MODULES


class Plan(models.Model):
    name = models.CharField(max_length=50, unique=True)
    max_learners = models.PositiveIntegerField(null=True, blank=True, help_text="Empty means unlimited")
    price_per_term = models.PositiveIntegerField(default=0, help_text="UGX")
    included_addons = models.JSONField(default=list, blank=True, help_text="Add-on keys included in the plan")
    addon_choices = models.PositiveSmallIntegerField(
        default=0, help_text="How many add-ons of the school's choice the plan includes"
    )
    priority_support = models.BooleanField(default=False)

    class Meta:
        ordering = ["price_per_term"]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        EXPIRED = "expired", "Expired"

    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    starts_on = models.DateField()
    ends_on = models.DateField()
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.school} — {self.plan} ({self.status})"


class SchoolModule(models.Model):
    """Platform switch for one add-on at one school. Data is never deleted when off."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="module_switches")
    module = models.CharField(max_length=30, choices=list(ALL_MODULES.items()))
    enabled = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    hidden_by_school = models.BooleanField(
        default=False, help_text="The school hid an enabled add-on it does not use yet"
    )
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    changed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "module"], name="uniq_school_module")]

    def __str__(self):
        return f"{self.school}: {self.module} {'on' if self.enabled else 'off'}"


class ModuleChangeLog(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    module = models.CharField(max_length=30)
    enabled = models.BooleanField()
    effective_from = models.DateField(null=True, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]


class SupportAccessGrant(models.Model):
    """The school lets the platform team read its records until expires_at."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="support_grants")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=300)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AccessRequest(models.Model):
    """A school asking to join, for a demo or for more information, sent from the public
    website. It reaches the platform team in the owner console, who follow it up."""

    class Kind(models.TextChoices):
        JOIN = "join", "Register our school"
        DEMO = "demo", "Book a demo"
        INFO = "info", "More information"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        DEMO_BOOKED = "demo_booked", "Demo booked"
        REGISTERED = "registered", "School registered"
        CLOSED = "closed", "Closed"

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.JOIN)
    school_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=150)
    role = models.CharField(max_length=60, blank=True, help_text="e.g. Director, Head teacher, DOS")
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    district = models.CharField(max_length=80, blank=True)
    levels = models.CharField(max_length=120, blank=True, help_text="Nursery, Primary, O-Level, A-Level")
    learners = models.PositiveIntegerField(null=True, blank=True, help_text="About how many learners")
    message = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)
    notes = models.TextField(blank=True, help_text="The platform team's follow-up notes")
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.school_name} ({self.get_kind_display()})"
