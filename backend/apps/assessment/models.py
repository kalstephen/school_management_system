import secrets

from django.conf import settings
from django.db import models

from apps.core.models import SchoolOwned
from apps.curriculum.models import Competency, Paper, Subject
from apps.learners.models import Learner
from apps.schoolsetup.models import SchoolClass, Stream, Term


class Exam(SchoolOwned):
    class Kind(models.TextChoices):
        BOT = "bot", "Beginning of term"
        MOT = "mot", "Mid-term"
        EOT = "eot", "End of term"
        MOCK = "mock", "Mock"
        CA = "ca", "Continuous assessment"
        OTHER = "other", "Other"

    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="exams")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=5, choices=Kind.choices)
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, default=100, help_text="Share of the term score"
    )
    max_mark = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    classes = models.ManyToManyField(SchoolClass, related_name="exams")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    schedule_published_at = models.DateTimeField(
        null=True, blank=True, help_text="Teachers see the exam timetable once the DOS publishes it"
    )

    class Meta:
        ordering = ["term", "start_date", "id"]

    def __str__(self):
        return f"{self.name} ({self.term})"


class ExamSchedule(SchoolOwned):
    """Exam timetable: when and where each paper is sat, and who invigilates."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="schedule")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    paper = models.ForeignKey(Paper, null=True, blank=True, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.ForeignKey("timetable.Room", null=True, blank=True, on_delete=models.SET_NULL)
    invigilator = models.ForeignKey("staff.StaffProfile", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["date", "start_time"]


class ExamSeat(SchoolOwned):
    """Where a learner sits for one exam session. Classes are mixed across rooms."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="seats")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="+")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="+")
    room = models.ForeignKey("timetable.Room", on_delete=models.CASCADE, related_name="+")
    seat = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["date", "start_time", "room__name", "seat"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "date", "start_time", "learner"], name="uniq_exam_seat")
        ]


class MarkSheet(SchoolOwned):
    """Marks for one exam, subject (or paper) and class/stream. Moves through
    draft → submitted → HOD reviewed → approved (locked). Returned sheets go back to the teacher."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted for approval"
        REVIEWED = "reviewed", "Reviewed by HOD"
        APPROVED = "approved", "Approved and locked"
        RETURNED = "returned", "Returned for correction"

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="mark_sheets")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    paper = models.ForeignKey(Paper, null=True, blank=True, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    return_comment = models.CharField(max_length=300, blank=True)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reopen_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "subject", "paper", "school_class", "stream"],
                name="uniq_mark_sheet",
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return f"{self.exam.name}: {self.paper or self.subject} {self.stream or self.school_class}"

    @property
    def is_editable(self):
        return self.status in (self.Status.DRAFT, self.Status.RETURNED)


class Mark(SchoolOwned):
    mark_sheet = models.ForeignKey(MarkSheet, on_delete=models.CASCADE, related_name="marks")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="marks")
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_absent = models.BooleanField(default=False, help_text="Missed the paper")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["mark_sheet", "learner"], name="uniq_mark")]

    def save(self, *args, **kwargs):
        if self.pk:
            self.version += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.learner}: {self.score}"


class AOIScore(SchoolOwned):
    """CBC activity-of-integration score (1–3) for one learner and competency in a term."""

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="aoi_scores")
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=3, decimal_places=1)
    remark = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "competency", "term"], name="uniq_aoi")]


class NurseryRating(SchoolOwned):
    class Rating(models.TextChoices):
        EXCELLENT = "excellent", "Excellent"
        VERY_GOOD = "very_good", "Very good"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        NEEDS_SUPPORT = "needs_support", "Needs support"

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="nursery_ratings")
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    learning_area = models.ForeignKey(Subject, on_delete=models.CASCADE)
    rating = models.CharField(max_length=15, choices=Rating.choices)
    remark = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["learner", "term", "learning_area"], name="uniq_nursery_rating")
        ]


class ResultSummary(SchoolOwned):
    """A learner's computed results for a term (from approved marks)."""

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="results")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="results")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.SET_NULL)
    rule_set = models.CharField(max_length=10)
    subjects = models.JSONField(default=list)
    total = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    average = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    aggregate = models.PositiveSmallIntegerField(null=True, blank=True)
    division = models.CharField(max_length=5, blank=True)
    points = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    position = models.PositiveIntegerField(null=True, blank=True)
    stream_position = models.PositiveIntegerField(null=True, blank=True)
    out_of = models.PositiveIntegerField(null=True, blank=True)
    is_complete = models.BooleanField(default=True, help_text="False when marks are missing")
    computed_at = models.DateTimeField(auto_now=True)

    audit_exclude = ("subjects",)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "term"], name="uniq_result")]


class CommentBank(SchoolOwned):
    """Preset report comments by mark range (teachers can edit them before approval).
    Class-teacher and head-teacher presets go by the learner's average; subject presets by
    the subject mark, either for one subject or for any subject."""

    class Role(models.TextChoices):
        CLASS_TEACHER = "class_teacher", "Class teacher"
        HEAD = "head", "Head teacher"
        SUBJECT = "subject", "Subject teacher"

    role = models.CharField(max_length=15, choices=Role.choices)
    subject = models.ForeignKey(
        "curriculum.Subject",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="Subject presets only; empty means any subject",
    )
    min_average = models.DecimalField(max_digits=5, decimal_places=2)
    max_average = models.DecimalField(max_digits=5, decimal_places=2)
    text = models.CharField(max_length=300)


class SubjectComment(SchoolOwned):
    """The subject teacher's comment on a learner for a term, printed beside the subject on
    the report card."""

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="subject_comments")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="+")
    subject = models.ForeignKey("curriculum.Subject", on_delete=models.CASCADE, related_name="+")
    text = models.CharField(max_length=300)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["learner", "term", "subject"], name="uniq_subject_comment")
        ]


def _token():
    return secrets.token_urlsafe(12)


class ReportCard(SchoolOwned):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        SUPERSEDED = "superseded", "Superseded"

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="report_cards")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="report_cards")
    result = models.ForeignKey(ResultSummary, on_delete=models.CASCADE, related_name="report_cards")
    serial = models.CharField(max_length=40, unique=True)
    verify_token = models.CharField(max_length=32, unique=True, default=_token)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    class_teacher_comment = models.CharField(max_length=500, blank=True)
    head_comment = models.CharField(max_length=500, blank=True)
    promotion_note = models.CharField(max_length=100, blank=True, help_text='e.g. "Promoted to P5"')
    snapshot = models.JSONField(
        default=dict, help_text="Results as published; never changes after publishing"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    audit_exclude = ("snapshot",)

    class Meta:
        ordering = ["learner__first_name"]


class UnebResult(SchoolOwned):
    """National results imported after UNEB releases them (PLE, UCE, UACE)."""

    class Level(models.TextChoices):
        PLE = "PLE", "PLE"
        UCE = "UCE", "UCE"
        UACE = "UACE", "UACE"

    year = models.PositiveSmallIntegerField()
    level = models.CharField(max_length=4, choices=Level.choices)
    index_number = models.CharField(max_length=30)
    candidate_name = models.CharField(max_length=200)
    learner = models.ForeignKey(
        Learner, null=True, blank=True, on_delete=models.SET_NULL, related_name="uneb_results"
    )
    sex = models.CharField(max_length=1, blank=True)
    subject_grades = models.JSONField(default=dict, help_text='{"ENG": "D2", "MTC": "C3", ...}')
    aggregate = models.PositiveSmallIntegerField(null=True, blank=True)
    division = models.CharField(max_length=10, blank=True, help_text="Division or overall result")
    points = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "year", "level", "index_number"], name="uniq_uneb_result"
            )
        ]
