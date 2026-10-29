import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Membership, RoleAssignment, User
from apps.core.models import School
from apps.learners.models import Enrolment, Learner
from apps.staff.models import StaffProfile


class SchoolFactory(DjangoModelFactory):
    class Meta:
        model = School

    name = factory.Sequence(lambda n: f"Test School {n}")
    short_name = factory.Sequence(lambda n: f"TS{n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "Pass-12345")

    @factory.post_generation
    def save_password(obj, create, extracted, **kwargs):
        if create:
            obj.save()


class LearnerFactory(DjangoModelFactory):
    class Meta:
        model = Learner

    adm_no = factory.Sequence(lambda n: f"2027/{n:04d}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    sex = factory.Iterator(["M", "F"])


class StaffFactory(DjangoModelFactory):
    class Meta:
        model = StaffProfile

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    kind = "teaching"


def make_user(school, *roles, username=None):
    """A user in `school` with roles given as 'role' or ('role', scope_type, scope_id)."""
    user = UserFactory(username=username) if username else UserFactory()
    membership = Membership.objects.create(school=school, user=user)
    for role in roles:
        if isinstance(role, tuple):
            name, scope_type, scope_id = role
        else:
            name, scope_type, scope_id = role, "school", None
        RoleAssignment.objects.create(
            school=school, membership=membership, role=name, scope_type=scope_type, scope_id=scope_id
        )
    return user


def enrol(learner, term, school_class, stream=None):
    return Enrolment.objects.create(
        school=learner.school, learner=learner, term=term, school_class=school_class, stream=stream
    )
