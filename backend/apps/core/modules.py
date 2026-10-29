"""Module registry: every module in the system, which ones a school has, and which of
those a particular user inherits."""

CORE_MODULES = {
    "setup": "School setup",
    "admissions": "Admissions & front desk",
    "learners": "Learners",
    "staff": "Staff & HR",
    "curriculum": "Academics & curriculum",
    "timetable": "Timetable",
    "attendance": "Attendance",
    "assessment": "Exams, assessment & report cards",
    "promotion": "Promotion",
    "discipline": "Discipline & welfare",
    "communication": "Communication",
    "finance": "Finance (expenditure)",
}

ADDON_MODULES = {
    "library": "Library",
    "sickbay": "Sickbay",
    "stores": "Stores, inventory & assets",
}

ALL_MODULES = {**CORE_MODULES, **ADDON_MODULES}

# Everything else depends on these, so a school always has them.
REQUIRED_MODULES = {"setup", "learners"}

MODULE_DESCRIPTIONS = {
    "setup": "Profile, academic years and terms, classes, streams, grading",
    "admissions": "Applications, interviews, admission numbers, visitors and enquiries",
    "learners": "Learner records, guardians, documents, transfers, CSV import",
    "staff": "Staff records, teaching load, leave, duty roster, staff attendance",
    "curriculum": "NCDC subjects, papers, combinations, allocations, schemes of work",
    "timetable": "Class, teacher and room timetables with clash detection",
    "attendance": "Daily and lesson roll call, chronic-absence flags",
    "assessment": "Exams, mark sheets and approval, PLE/CBC/UACE grading, report cards, UNEB",
    "promotion": "End-of-year promotion rules, review and approval",
    "discipline": "Discipline cases, counselling, achievements",
    "communication": "Notices, circulars, email to guardians, calendar",
    "finance": "Expenses, petty cash, budgets, suppliers, reports (no fees)",
    "library": "Catalogue, issue and return, overdue lists",
    "sickbay": "Sickbay visits, treatment, immunisations",
    "stores": "Stock, scholastic requirements, asset register",
}


def module_enabled(school, module):
    """Is the module switched on for the school?

    Required modules are always on. Otherwise the platform's switch decides; a school
    with no switch recorded has every core module and no add-ons (the original default)."""
    if module not in ALL_MODULES:
        return False
    if module in REQUIRED_MODULES:
        return True
    from django.utils import timezone

    from apps.subscriptions.models import SchoolModule

    row = SchoolModule.objects.filter(school=school, module=module).first()
    if row is None:
        return module in CORE_MODULES
    if not row.enabled or row.hidden_by_school:
        return False
    return row.effective_from is None or row.effective_from <= timezone.localdate()


def enabled_modules(school):
    return [m for m in ALL_MODULES if module_enabled(school, m)]


def user_modules(user, school):
    """Modules this user can open: the school's modules, narrowed to the user's own list
    when one is set (an empty list means "everything the school has")."""
    school_modules = enabled_modules(school)
    if not user.is_authenticated:
        return []
    from apps.accounts.models import Membership

    membership = Membership.objects.filter(user=user, school=school, is_active=True).first()
    if membership is None or not membership.modules:
        return school_modules
    allowed = set(membership.modules) | REQUIRED_MODULES
    return [m for m in school_modules if m in allowed]


def user_module_enabled(request, module):
    """Module check for a request: cached per request."""
    if not hasattr(request, "_user_modules"):
        request._user_modules = set(user_modules(request.user, request.school))
    return module in request._user_modules
