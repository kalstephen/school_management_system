from django.db import connection

from .context import reset_context, reset_platform_session, set_context, set_platform_session


def _set_db_school(school):
    """Tell PostgreSQL which school this request belongs to, for row-level security."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_school', %s, false)", [str(school.pk) if school else ""]
        )


class SchoolContextMiddleware:
    """Resolve the active school for the signed-in user and expose it as request.school."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.accounts.services import platform_session, resolve_school

        user = request.user if request.user.is_authenticated else None
        request.is_platform_session = bool(user) and platform_session(request)
        school = resolve_school(request, user) if user else None
        # The owner console sets up a school's classes, terms, profile and grading by naming
        # it in X-Setup-School. Only views marked platform_setup accept such requests.
        request.platform_setup = False
        # File links (PDF previews) cannot send headers, so they carry ?setup_school.
        setup_school = request.headers.get("X-Setup-School") or request.GET.get("setup_school")
        if request.is_platform_session and setup_school and setup_school.isdigit():
            from apps.core.models import School

            school = School.objects.filter(pk=int(setup_school)).first()
            request.platform_setup = school is not None
        request.school = school
        tokens = set_context(user, school)
        platform_token = set_platform_session(request.is_platform_session)
        _set_db_school(school)
        try:
            return self.get_response(request)
        finally:
            reset_platform_session(platform_token)
            reset_context(tokens)
