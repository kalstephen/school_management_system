from django.conf import settings
from django.db import models

from apps.core.models import SchoolOwned
from apps.schoolsetup.models import Department


class StaffProfile(SchoolOwned):
    class Kind(models.TextChoices):
        TEACHING = "teaching", "Teaching"
        NON_TEACHING = "non_teaching", "Non-teaching"

    class Contract(models.TextChoices):
        PERMANENT = "permanent", "Permanent"
        CONTRACT = "contract", "Contract"
        PART_TIME = "part_time", "Part-time"
        VOLUNTEER = "volunteer", "Volunteer"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ON_LEAVE = "on_leave", "On leave"
        LEFT = "left", "Left"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_profiles",
    )
    staff_no = models.CharField(max_length=30, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=1, choices=[("M", "Male"), ("F", "Female")], blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nin = models.CharField("National ID (NIN)", max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to="staff/", blank=True)
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.TEACHING)
    designation = models.CharField(max_length=100, blank=True)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="staff"
    )
    tmis_number = models.CharField("TMIS number", max_length=30, blank=True)
    registration_number = models.CharField(max_length=30, blank=True, help_text="Teacher registration number")
    highest_qualification = models.CharField(max_length=100, blank=True)
    subjects = models.ManyToManyField(
        "curriculum.Subject",
        blank=True,
        related_name="specialists",
        help_text="Subjects the teacher can teach, at any level; used to suggest who teaches what",
    )
    specialisation = models.CharField(max_length=200, blank=True)
    contract_type = models.CharField(max_length=15, choices=Contract.choices, default=Contract.PERMANENT)
    contract_start = models.DateField(null=True, blank=True)
    contract_end = models.DateField(null=True, blank=True)
    max_periods_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name = "staff member"

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Qualification(SchoolOwned):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="qualifications")
    title = models.CharField(max_length=200)
    institution = models.CharField(max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    document = models.FileField(upload_to="qualifications/", blank=True)

    def __str__(self):
        return self.title


class LeaveRequest(SchoolOwned):
    class Kind(models.TextChoices):
        ANNUAL = "annual", "Annual"
        SICK = "sick", "Sick"
        MATERNITY = "maternity", "Maternity"
        PATERNITY = "paternity", "Paternity"
        STUDY = "study", "Study"
        COMPASSIONATE = "compassionate", "Compassionate"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="leave_requests")
    kind = models.CharField(max_length=15, choices=Kind.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-start_date"]

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


class DutyRoster(SchoolOwned):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="duties")
    date = models.DateField()
    duty = models.CharField(max_length=100, help_text="e.g. Teacher on duty, Gate, Dining hall")
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["date"]


class StaffAttendance(SchoolOwned):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        LEAVE = "leave", "On leave"

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    time_in = models.TimeField(null=True, blank=True)
    time_out = models.TimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["staff", "date"], name="uniq_staff_day")]


class PlannerTask(SchoolOwned):
    """One item on a teacher's weekly work planner (to-do list)."""

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="planner_tasks")
    week_start = models.DateField(help_text="Monday of the week", db_index=True)
    day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[
            (1, "Monday"),
            (2, "Tuesday"),
            (3, "Wednesday"),
            (4, "Thursday"),
            (5, "Friday"),
            (6, "Saturday"),
            (7, "Sunday"),
        ],
    )
    title = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    school_class = models.ForeignKey(
        "schoolsetup.SchoolClass", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    priority = models.CharField(max_length=6, choices=Priority.choices, default=Priority.NORMAL)
    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["week_start", "done", "day", "id"]

    def __str__(self):
        return self.title
