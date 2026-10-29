from rest_framework.permissions import SAFE_METHODS, BasePermission

from .modules import user_module_enabled


def has_perm(request, perm):
    from apps.accounts.services import effective_perms

    if perm is None:
        return True
    if not hasattr(request, "_school_perms"):
        request._school_perms = effective_perms(request.user, getattr(request, "school", None))
    return perm in request._school_perms


class SchoolPermission(BasePermission):
    """Checks, in order: an active school, the module is on, the subscription allows the
    request, and the user's roles grant the permission the view asks for."""

    message = "You do not have permission to do this."

    def has_permission(self, request, view):
        from apps.subscriptions.services import school_access

        if getattr(request, "platform_setup", False):
            # The owner console setting up a school: setup views only, never school records.
            allowed = getattr(view, "platform_setup", False)
            if allowed == "read":
                allowed = request.method in SAFE_METHODS
            if not allowed:
                self.message = "The owner console can only change a school's setup."
            return bool(allowed)
        school = getattr(request, "school", None)
        if school is None:
            self.message = "No active school is selected for your account."
            return False
        module = getattr(view, "module", None)
        if module and not user_module_enabled(request, module):
            self.message = "This module is not enabled for your school or your account."
            return False
        access = school_access(school)
        if access == "suspended":
            self.message = "This school's subscription is suspended."
            return False
        if access == "read_only" and request.method not in SAFE_METHODS:
            self.message = "The subscription has expired; the school is read-only (view and export)."
            return False
        perm = view.get_required_perm(request) if hasattr(view, "get_required_perm") else None
        return has_perm(request, perm)
