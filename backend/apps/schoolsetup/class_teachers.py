"""Class teachers and deputy class teachers.

Each class, and each stream of a class (P1 East, P1 West), has at most one class teacher
and one deputy. Both get class-teacher access to it (register, marks, report comments,
enrolment, promotion review). A teacher is class teacher of one class or stream at a time;
appointing them elsewhere moves them, and appointing someone to a post that is taken
replaces the holder. The DOS, head teacher, director and school administrator appoint
(classes.assign); nobody appoints themselves except the director.
"""

from django.db import transaction

from apps.core.exceptions import BusinessRuleError

from .models import SchoolClass, Stream

POSTS = {"class_teacher": "Class teacher", "deputy": "Deputy class teacher"}
FIELD = {"class_teacher": "class_teacher", "deputy": "deputy_class_teacher"}


def target_key(target):
    return f"{'stream' if isinstance(target, Stream) else 'class'}:{target.pk}"


def parse_target(school, value):
    """'class:12' or 'stream:5' to the class or stream, or None for an empty value."""
    if not value:
        return None
    kind, _, pk = str(value).partition(":")
    model = {"class": SchoolClass, "stream": Stream}.get(kind)
    target = model.objects.filter(school=school, pk=pk).first() if model and pk.isdigit() else None
    if target is None:
        raise BusinessRuleError({"target": "Choose a class or stream from the list."})
    return target


def targets(school):
    """Every class and stream a class teacher can be appointed to, with the current holders."""
    rows = []
    for school_class in (
        SchoolClass.objects.filter(school=school)
        .select_related("class_teacher", "deputy_class_teacher")
        .prefetch_related("streams__class_teacher", "streams__deputy_class_teacher")
        .order_by("order")
    ):
        streams = list(school_class.streams.all())
        for target, label in [(school_class, school_class.name + (" (whole class)" if streams else ""))] + [
            (s, str(s)) for s in streams
        ]:
            rows.append(
                {
                    "key": target_key(target),
                    "label": label,
                    "class_teacher": target.class_teacher_id,
                    "class_teacher_name": target.class_teacher.full_name if target.class_teacher else None,
                    "deputy": target.deputy_class_teacher_id,
                    "deputy_name": (
                        target.deputy_class_teacher.full_name if target.deputy_class_teacher else None
                    ),
                }
            )
    return rows


def posts_of(staff):
    """The class-teacher posts a staff member holds."""
    rows = []
    for post, field in FIELD.items():
        for model in (SchoolClass, Stream):
            for target in model.objects.filter(**{field: staff}):
                rows.append(
                    {
                        "post": post,
                        "post_label": POSTS[post],
                        "target": target_key(target),
                        "label": str(target),
                    }
                )
    return rows


def sync_access(target):
    """Class-teacher access to this class or stream for exactly its class teacher and deputy."""
    from apps.accounts.models import Membership, RoleAssignment

    school = target.school
    scope_type = "stream" if isinstance(target, Stream) else "class"
    holders = {t.user_id for t in (target.class_teacher, target.deputy_class_teacher) if t and t.user_id}
    RoleAssignment.objects.filter(
        school=school, role="class_teacher", scope_type=scope_type, scope_id=target.pk
    ).exclude(membership__user_id__in=holders).delete()
    for user_id in holders:
        membership, _ = Membership.objects.get_or_create(school=school, user_id=user_id)
        RoleAssignment.objects.get_or_create(
            school=school,
            membership=membership,
            role="class_teacher",
            scope_type=scope_type,
            scope_id=target.pk,
        )


def _check_appointer(user, school, staff):
    from apps.accounts.services import user_roles

    if staff is not None and staff.user_id and staff.user_id == user.pk:
        if not user_roles(user, school).filter(role="director").exists():
            raise BusinessRuleError(
                {"detail": "You cannot appoint yourself. The DOS, head teacher or director sets this."}
            )


def assign(target, post, staff, by_user):
    """Make `staff` the class teacher (or deputy) of `target`, or clear the post (staff=None)."""
    if post not in FIELD:
        raise BusinessRuleError({"post": "Choose class teacher or deputy class teacher."})
    if staff is not None and staff.school_id != target.school_id:
        raise BusinessRuleError({"staff": "Choose a member of your staff."})
    _check_appointer(by_user, target.school, staff)
    field = FIELD[post]
    other = FIELD["deputy" if post == "class_teacher" else "class_teacher"]
    touched = [target]
    with transaction.atomic():
        if staff is not None:
            # The same person cannot be both class teacher and deputy of one class.
            if getattr(target, other + "_id") == staff.pk:
                setattr(target, other, None)
            # A teacher leads one class at a time: appointing them elsewhere moves them.
            if post == "class_teacher":
                for model in (SchoolClass, Stream):
                    for previous in model.objects.filter(class_teacher=staff).exclude(
                        pk=target.pk if isinstance(target, model) else None
                    ):
                        previous.class_teacher = None
                        previous.save(update_fields=["class_teacher"])
                        touched.append(previous)
        setattr(target, field, staff)
        target.save(update_fields=["class_teacher", "deputy_class_teacher"])
        for item in touched:
            sync_access(item)
    return target


def set_posts_for_staff(staff, post, value, by_user):
    """From the staff form: put this person in the post for `value` ('class:12'), or take them
    out of that kind of post when `value` is empty."""
    target = parse_target(staff.school, value)
    if target is not None:
        assign(target, post, staff, by_user)
        return
    _check_appointer(by_user, staff.school, staff)
    field = FIELD[post]
    with transaction.atomic():
        for model in (SchoolClass, Stream):
            for item in model.objects.filter(**{field: staff}):
                setattr(item, field, None)
                item.save(update_fields=[field])
                sync_access(item)
