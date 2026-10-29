import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.schoolsetup.defaults import seed_school_defaults
from apps.schoolsetup.models import AcademicYear, SchoolClass, Term

from .factories import LearnerFactory, SchoolFactory, StaffFactory, enrol, make_user


@pytest.fixture(autouse=True)
def _fast_passwords(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def school(db):
    school = SchoolFactory(name="Kampala Model Primary School")
    seed_school_defaults(school, ["nursery", "primary", "olevel", "alevel"])
    return school


@pytest.fixture
def other_school(db):
    school = SchoolFactory(name="Other School")
    seed_school_defaults(school, ["primary"])
    return school


@pytest.fixture
def year(school, today):
    return AcademicYear.objects.create(
        school=school,
        name=str(today.year),
        start_date=today - datetime.timedelta(days=60),
        end_date=today + datetime.timedelta(days=200),
        is_current=True,
    )


@pytest.fixture
def term(school, year, today):
    return Term.objects.create(
        school=school,
        academic_year=year,
        number=1,
        start_date=today - datetime.timedelta(days=30),
        end_date=today + datetime.timedelta(days=60),
        status="open",
    )


@pytest.fixture
def p5(school):
    return SchoolClass.objects.get(school=school, name="P5")


@pytest.fixture
def p7(school):
    return SchoolClass.objects.get(school=school, name="P7")


@pytest.fixture
def learners(school, term, p5):
    rows = []
    for _ in range(4):
        learner = LearnerFactory(school=school)
        enrol(learner, term, p5)
        rows.append(learner)
    return rows


@pytest.fixture
def head(school):
    return make_user(school, "head_teacher", username="head")


@pytest.fixture
def dos(school):
    return make_user(school, "dos", username="dos")


@pytest.fixture
def bursar(school):
    return make_user(school, "bursar", username="bursar")


@pytest.fixture
def director(school):
    return make_user(school, "director", username="director")


@pytest.fixture
def nurse(school):
    return make_user(school, "nurse", username="nurse")


@pytest.fixture
def teacher_factory(school):
    """A subject teacher allocated to (subject, class) pairs."""
    from apps.curriculum.models import SubjectAllocation

    def build(*pairs, extra_roles=()):
        user = make_user(school, "subject_teacher", *extra_roles)
        staff = StaffFactory(school=school, user=user)
        for subject, school_class in pairs:
            SubjectAllocation.objects.create(
                school=school, teacher=staff, subject=subject, school_class=school_class
            )
        return user

    return build


@pytest.fixture
def setup_client(school, client_for):
    """The owner console setting up `school` (school setup is done there, not in the school)."""
    from .factories import UserFactory

    client = client_for(UserFactory(is_platform_admin=True))
    client.credentials(HTTP_X_SETUP_SCHOOL=str(school.id))
    return client


@pytest.fixture
def client_for():
    """A signed-in client. Platform-team accounts get a platform-console session; everyone
    else a school-portal session, as if they had signed in through that door."""

    def build(user):
        client = APIClient()
        client.force_login(user)
        session = client.session
        session["portal"] = "platform" if (user.is_platform_admin or user.is_superuser) else "school"
        session.save()
        return client

    return build
