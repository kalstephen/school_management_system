from django.conf import settings
from django.db import models

from apps.core.models import SchoolOwned
from apps.learners.models import Learner
from apps.schoolsetup.models import SchoolClass, Section, Stream, Term


class PromotionRule(SchoolOwned):
    class Measure(models.TextChoices):
        TERM3_AVERAGE = "term3_average", "Term 3 average (%)"
        ANNUAL_AVERAGE = "annual_average", "Average of all three terms (%)"
        PLE_AGGREGATE = "ple_aggregate", "PLE-style aggregate (lower is better)"
        SUBJECTS_FAILED = "subjects_failed", "Number of subjects failed (lower is better)"
        ATTENDANCE = "attendance", "Attendance rate (%)"

    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.CASCADE)
    school_class = models.ForeignKey(
        SchoolClass,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="A class rule overrides the section rule",
    )
    measure = models.CharField(max_length=20, choices=Measure.choices)
    pass_mark = models.DecimalField(max_digits=6, decimal_places=2)
    probation_mark = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Learners between this and the pass mark are promoted on probation",
    )
    fail_below = models.DecimalField(
        max_digits=5, decimal_places=2, default=50, help_text="For 'subjects failed'"
    )
    min_attendance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional extra condition: minimum attendance rate (%)",
    )

    def __str__(self):
        return f"{self.school_class or self.section}: {self.get_measure_display()} {self.pass_mark}"

    @property
    def lower_is_better(self):
        return self.measure in (self.Measure.PLE_AGGREGATE, self.Measure.SUBJECTS_FAILED)


class PromotionBatch(SchoolOwned):
    """One class's promotion list for a year. It passes three desks: the class teacher
    reviews it, the Director of Studies recommends it and the director (or head teacher)
    approves it. The DOS and the director may change any learner's decision on the way."""

    class Status(models.TextChoices):
        PROPOSED = "proposed", "With the class teacher"
        SUBMITTED = "submitted", "Reviewed by class teacher, with the DOS"
        RECOMMENDED = "recommended", "Recommended by the DOS, with the director"
        APPROVED = "approved", "Approved"
        APPLIED = "applied", "Applied to the new year"
        UNDONE = "undone", "Undone"

    term = models.ForeignKey(Term, on_delete=models.CASCADE, help_text="Normally Term 3")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    rule = models.ForeignKey(PromotionRule, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROPOSED)
    pass_mark = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, help_text="The mark used for this list"
    )
    stream_policy = models.CharField(
        max_length=12,
        default="keep",
        choices=[
            ("keep", "Keep streams"),
            ("balance", "Rebalance by number"),
            ("performance", "Rebalance by performance"),
        ],
    )
    target_term = models.ForeignKey(Term, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    teacher_note = models.CharField(max_length=500, blank=True)
    recommended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    recommended_at = models.DateTimeField(null=True, blank=True)
    dos_note = models.CharField(max_length=500, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    director_note = models.CharField(max_length=500, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class PromotionDecision(SchoolOwned):
    class Outcome(models.TextChoices):
        PROMOTE = "promote", "Promote"
        PROBATION = "probation", "Promote on probation"
        REPEAT = "repeat", "Repeat"
        DEMOTE = "demote", "Demote to the class below"
        COMPLETE = "complete", "Completed (candidate class)"
        REVIEW = "review", "Needs review (missing marks)"

    batch = models.ForeignKey(PromotionBatch, on_delete=models.CASCADE, related_name="decisions")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="promotion_decisions")
    measure_value = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    proposed = models.CharField(max_length=10, choices=Outcome.choices)
    final = models.CharField(max_length=10, choices=Outcome.choices)
    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    override_reason = models.CharField(max_length=300, blank=True)
    teacher_comment = models.CharField(max_length=300, blank=True)
    to_class = models.ForeignKey(
        SchoolClass, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    to_stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_enrolment = models.ForeignKey(
        "learners.Enrolment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "learner"], name="uniq_promotion_decision")]
