"""Content manager (Django admin with the Unfold theme).

For the platform team and school administrators who need to look at or correct any
record directly. Every model in the project is registered with sensible list columns,
search and filters; school users see only their own school's rows.
"""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import models
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from apps.accounts.models import Membership, RoleAssignment, User

from .models import AccessLog, AuditLog, School, SchoolOwned

PROJECT_APPS = [
    "core",
    "accounts",
    "subscriptions",
    "schoolsetup",
    "curriculum",
    "learners",
    "admissions",
    "staff",
    "timetable",
    "attendance",
    "assessment",
    "promotion",
    "discipline",
    "communication",
    "finance",
    "library",
    "sickbay",
    "stores",
    "sync",
]
SEARCHABLE = (models.CharField, models.EmailField)
FILTERABLE = (models.BooleanField, models.ForeignKey)
SKIP_COLUMNS = {"created_by", "updated_by", "created_at", "updated_at", "school", "password"}


class SchoolScopedAdmin(ModelAdmin):
    """Generic admin: non-superusers only see rows for schools they belong to."""

    list_per_page = 50
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser or not issubclass(self.model, SchoolOwned):
            return queryset
        return queryset.filter(school_id__in=request.user.memberships.values("school_id"))

    def save_model(self, request, obj, form, change):
        if isinstance(obj, SchoolOwned) and not obj.school_id:
            membership = request.user.memberships.first()
            if membership:
                obj.school_id = membership.school_id
        super().save_model(request, obj, form, change)


def _admin_for(model):
    fields = [
        f
        for f in model._meta.concrete_fields
        if f.name not in SKIP_COLUMNS and not isinstance(f, models.JSONField)
    ]
    columns = [f.name for f in fields if not isinstance(f, (models.TextField, models.FileField))][:7] or [
        "__str__"
    ]
    search = [f.name for f in fields if isinstance(f, SEARCHABLE)][:5]
    filters = [f.name for f in fields if isinstance(f, FILTERABLE) and f.name != "school"][:4]
    if issubclass(model, SchoolOwned):
        filters = ["school", *filters]
    attrs = {
        "list_display": columns,
        "search_fields": search,
        "list_filter": filters,
        "readonly_fields": tuple(n for n in SchoolScopedAdmin.readonly_fields if hasattr(model, n)),
    }
    return type(f"{model.__name__}Admin", (SchoolScopedAdmin,), attrs)


class RoleInline(TabularInline):
    model = RoleAssignment
    fk_name = "membership"
    extra = 0
    fields = ("role", "scope_type", "scope_id")

    def save_formset(self, request, form, formset, change):  # pragma: no cover - admin glue
        super().save_formset(request, form, formset, change)


class MembershipInline(TabularInline):
    model = Membership
    fk_name = "user"
    extra = 0
    fields = ("school", "title", "is_active")


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
        "is_platform_admin",
        "is_active",
        "last_login",
    )
    list_filter = ("is_platform_admin", "is_active", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("School system", {"fields": ("phone", "is_platform_admin", "locked_until")}),
    )
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(SchoolScopedAdmin):
    list_display = ("user", "school", "title", "is_active")
    list_filter = ("school", "is_active")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    inlines = [RoleInline]

    def save_formset(self, request, form, formset, change):
        for obj in formset.save(commit=False):
            obj.school_id = form.instance.school_id
            obj.save()
        formset.save_m2m()


@admin.register(School)
class SchoolAdmin(ModelAdmin):
    list_display = ("name", "short_name", "kind", "phone", "email", "is_active", "created_at")
    search_fields = ("name", "short_name", "email", "emis_number")
    list_filter = ("kind", "is_active")


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ("timestamp", "school", "user", "action", "entity", "object_repr")
    list_filter = ("action", "school", "entity")
    search_fields = ("object_repr", "entity", "object_id")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccessLog)
class AccessLogAdmin(AuditLogAdmin):
    list_display = ("timestamp", "school", "user", "resource", "object_id")
    list_filter = ("school", "resource")
    search_fields = ("resource", "object_id")
    readonly_fields = [f.name for f in AccessLog._meta.fields]


def register_everything():
    for label in PROJECT_APPS:
        for model in apps.get_app_config(label).get_models():
            if not admin.site.is_registered(model):
                admin.site.register(model, _admin_for(model))


register_everything()
admin.site.site_header = "Content Manager"
admin.site.site_title = "School Management — Content Manager"
admin.site.index_title = "Manage school records"
