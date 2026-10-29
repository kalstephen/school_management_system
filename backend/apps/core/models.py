import re

from django.conf import settings
from django.db import models, transaction

from .context import get_current_user

DEFAULT_ADM_FORMAT = "{year}/{seq:04d}"


def make_school_code(name, exclude_pk=None):
    """A readable school ID such as NewHope-003: the first two words of the name in
    CamelCase, then a running number across the platform."""
    words = re.findall(r"[A-Za-z0-9]+", name or "School")
    stem = "".join(w[:1].upper() + w[1:].lower() for w in words[:2]) or "School"
    number = School.objects.count() + 1
    while True:
        code = f"{stem[:20]}-{number:03d}"
        if not School.objects.filter(code__iexact=code).exclude(pk=exclude_pk).exists():
            return code
        number += 1


class School(models.Model):
    class Kind(models.TextChoices):
        DAY = "day", "Day"
        BOARDING = "boarding", "Boarding"
        MIXED = "mixed", "Day and boarding"

    class Ownership(models.TextChoices):
        GOVERNMENT = "government", "Government"
        PRIVATE = "private", "Private"
        COMMUNITY = "community", "Community"
        FAITH = "faith", "Faith-based"
        INTERNATIONAL = "international", "International"

    class Levels(models.TextChoices):
        NURSERY = "nursery", "Nursery only"
        PRIMARY = "primary", "Nursery and primary"
        SECONDARY = "secondary", "Secondary (O and A-Level)"
        O_LEVEL = "olevel", "O-Level only"
        ALL = "all", "Nursery to A-Level"

    # Identity
    code = models.CharField(
        "School ID",
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text="Used at sign-in, e.g. NewHope-003. Generated from the name if left empty.",
    )
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50, blank=True)
    motto = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField("MoES registration number", max_length=50, blank=True)
    ownership = models.CharField(max_length=15, choices=Ownership.choices, default=Ownership.PRIVATE)
    levels = models.CharField("Levels offered", max_length=10, choices=Levels.choices, default=Levels.PRIMARY)
    established = models.PositiveSmallIntegerField("Year established", null=True, blank=True)
    # Location
    region = models.CharField(max_length=50, blank=True, help_text="Central, Eastern, Northern, Western")
    district = models.CharField(max_length=100, blank=True)
    county = models.CharField("County / municipality", max_length=100, blank=True)
    sub_county = models.CharField("Sub-county / division", max_length=100, blank=True)
    parish = models.CharField("Parish / ward", max_length=100, blank=True)
    village = models.CharField("Village / cell", max_length=100, blank=True)
    address = models.CharField(max_length=300, blank=True)
    gps = models.CharField("GPS coordinates", max_length=60, blank=True)
    # Contacts
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="logos/", blank=True)
    # Head teacher
    head_teacher_name = models.CharField(max_length=200, blank=True)
    head_teacher_phone = models.CharField(max_length=50, blank=True)
    head_teacher_email = models.EmailField(blank=True)
    # Director / proprietor profile
    director_name = models.CharField(max_length=200, blank=True)
    director_phone = models.CharField(max_length=50, blank=True)
    director_email = models.EmailField(blank=True)
    director_nin = models.CharField("Director NIN", max_length=20, blank=True)
    director_address = models.CharField(max_length=300, blank=True)
    emis_number = models.CharField("EMIS number", max_length=50, blank=True)
    uneb_centre_number = models.CharField("UNEB centre number", max_length=50, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.DAY)
    adm_no_format = models.CharField(
        max_length=50, default=DEFAULT_ADM_FORMAT, help_text="Admission number pattern, e.g. {year}/{seq:04d}"
    )
    next_adm_seq = models.PositiveIntegerField(default=1)
    other_income_enabled = models.BooleanField(default=True)
    report_card_footer = models.CharField(max_length=300, blank=True)
    report_template = models.CharField(
        max_length=20,
        default="classic",
        choices=[
            ("classic", "Classic"),
            ("modern", "Modern banner"),
            ("prestige", "Prestige letterhead"),
            ("compact", "Compact"),
        ],
        help_text="Report card design, agreed with the school and set by the platform owners",
    )
    report_color = models.CharField(
        max_length=7, default="#1d4ed8", help_text="Main colour of the report card"
    )
    report_show_photo = models.BooleanField(
        default=True, help_text="Print the learner's photo on report cards"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = make_school_code(self.name, exclude_pk=self.pk)
        super().save(*args, **kwargs)

    @property
    def location(self):
        return ", ".join(p for p in [self.village, self.parish, self.sub_county, self.district] if p)

    def next_admission_number(self, year):
        """Reserve and return the next admission number. Call inside a transaction."""
        from apps.learners.models import Learner

        school = School.objects.select_for_update().get(pk=self.pk)
        # A pattern without {seq} (e.g. an example typed in by mistake) would repeat one number.
        pattern = school.adm_no_format if "{seq" in school.adm_no_format else DEFAULT_ADM_FORMAT
        while True:
            try:
                number = pattern.format(year=year, seq=school.next_adm_seq)
            except (KeyError, IndexError, ValueError):
                pattern = DEFAULT_ADM_FORMAT
                continue
            school.next_adm_seq += 1
            if not Learner.objects.filter(school=school, adm_no=number).exists():
                break
        school.save(update_fields=["next_adm_seq"])
        self.next_adm_seq = school.next_adm_seq
        return number


class SchoolOwned(models.Model):
    """Base for every school record: school isolation, audit columns and audit log."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="+", editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Fields never written to the audit log (large or derived values).
    audit_exclude = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from .audit import record_save

        user = get_current_user()
        if user is not None and user.is_authenticated:
            if self.pk is None:
                self.created_by = user
            self.updated_by = user
        old = None
        if self.pk is not None:
            old = type(self).objects.filter(pk=self.pk).values().first()
        with transaction.atomic():
            super().save(*args, **kwargs)
            record_save(self, old)

    def delete(self, *args, **kwargs):
        from .audit import record_delete

        with transaction.atomic():
            record_delete(self)
            return super().delete(*args, **kwargs)


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DELETE = "delete", "Deleted"

    school = models.ForeignKey(School, null=True, on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    entity = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=64, db_index=True)
    object_repr = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=10, choices=Action.choices)
    changes = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        return f"{self.action} {self.entity}#{self.object_id}"


class AccessLog(models.Model):
    """Reads of sensitive records (health) — the concept requires every view to be logged."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    resource = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
