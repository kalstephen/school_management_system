from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.core.models import School, SchoolOwned

from .roles import ALL_PERMS, ROLE_LABELS


class User(AbstractUser):
    """A person who can log in. Staff only: there are no parent or learner logins."""

    phone = models.CharField(max_length=30, blank=True)
    is_platform_admin = models.BooleanField(
        default=False, help_text="Platform team: manages schools and plans, cannot read school records."
    )
    failed_logins = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    def is_locked(self):
        return self.locked_until is not None and self.locked_until > timezone.now()

    @property
    def display_name(self):
        return self.get_full_name() or self.username


class Membership(SchoolOwned):
    """Links a user to a school. A teacher who works at two schools has two memberships."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    is_active = models.BooleanField(default=True)
    title = models.CharField(max_length=100, blank=True)
    modules = models.JSONField(
        default=list,
        blank=True,
        help_text="Modules this person may open; empty means every module the school has",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "user"], name="uniq_membership")]

    def __str__(self):
        return f"{self.user} @ {self.school}"


class RoleAssignment(SchoolOwned):
    class Scope(models.TextChoices):
        SCHOOL = "school", "Whole school"
        SECTION = "section", "Section"
        CLASS = "class", "Class"
        STREAM = "stream", "Stream"
        DEPARTMENT = "department", "Department"
        STORE = "store", "Store"

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="roles")
    role = models.CharField(max_length=30, choices=list(ROLE_LABELS.items()))
    scope_type = models.CharField(max_length=20, choices=Scope.choices, default=Scope.SCHOOL)
    scope_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role", "scope_type", "scope_id"], name="uniq_role_scope"
            )
        ]

    def __str__(self):
        scope = "" if self.scope_type == "school" else f" ({self.scope_type} {self.scope_id})"
        return f"{self.get_role_display()}{scope}"


class PermissionGrant(SchoolOwned):
    """A time-limited exception: one extra permission until expires_at."""

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="grants")
    permission = models.CharField(max_length=50, choices=[(p, p) for p in ALL_PERMS])
    reason = models.CharField(max_length=300)
    expires_at = models.DateTimeField()

    def is_active(self):
        return self.expires_at > timezone.now()

    def __str__(self):
        return f"{self.permission} until {self.expires_at:%Y-%m-%d}"


__all__ = ["User", "Membership", "RoleAssignment", "PermissionGrant", "School"]
