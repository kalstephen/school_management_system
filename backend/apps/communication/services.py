from django.core.mail import EmailMessage
from django.utils import timezone

from apps.accounts.models import Membership, RoleAssignment

from .models import EmailLog, Notice, Notification

TEACHING_ROLES = {"head_teacher", "dos", "hod", "class_teacher", "subject_teacher"}


def notice_recipients(notice):
    members = Membership.objects.filter(school=notice.school, is_active=True)
    if notice.audience == Notice.Audience.ALL_STAFF:
        return [m.user for m in members.select_related("user")]
    roles = TEACHING_ROLES if notice.audience == Notice.Audience.TEACHERS else set(notice.roles)
    user_ids = RoleAssignment.objects.filter(school=notice.school, role__in=roles).values_list(
        "membership__user_id", flat=True
    )
    return [m.user for m in members.filter(user_id__in=user_ids).select_related("user")]


def notify(school, users, title, body="", link=""):
    Notification.objects.bulk_create(
        [Notification(school=school, user=u, title=title, body=body[:500], link=link) for u in users]
    )


def _send(school, to, subject, body, kind, attachments=()):
    try:
        message = EmailMessage(subject, body, to=[to])
        for name, content, mimetype in attachments:
            message.attach(name, content, mimetype)
        message.send()
        EmailLog.objects.create(
            school=school, to=to, subject=subject[:200], kind=kind, status=EmailLog.Status.SENT
        )
        return True
    except Exception as exc:  # noqa: BLE001 — any transport error is logged, not raised
        EmailLog.objects.create(
            school=school,
            to=to,
            subject=subject[:200],
            kind=kind,
            status=EmailLog.Status.FAILED,
            error=str(exc)[:500],
        )
        return False


def guardian_emails(school, class_ids=None):
    from apps.learners.models import Enrolment, LearnerGuardian
    from apps.schoolsetup.models import current_term

    links = LearnerGuardian.objects.filter(
        school=school, receives_email=True, learner__status="active"
    ).exclude(guardian__email="")
    if class_ids:
        term = current_term(school)
        learner_ids = Enrolment.objects.filter(term=term, school_class_id__in=class_ids).values("learner_id")
        links = links.filter(learner_id__in=learner_ids)
    return sorted(set(links.values_list("guardian__email", flat=True)))


def publish_notice(notice):
    notice.published_at = timezone.now()
    notice.save()
    users = notice_recipients(notice)
    notify(notice.school, users, notice.title, notice.body, link=f"/notices/{notice.id}")
    sent = failed = 0
    if notice.email_guardians:
        class_ids = list(notice.guardian_classes.values_list("id", flat=True))
        for email in guardian_emails(notice.school, class_ids):
            ok = _send(notice.school, email, f"{notice.school.name}: {notice.title}", notice.body, "notice")
            sent, failed = sent + ok, failed + (not ok)
    return {"staff_notified": len(users), "emails_sent": sent, "emails_failed": failed}


def email_report_cards(school, cards):
    from apps.assessment.pdf import render_cards

    sent = failed = skipped = 0
    for card in cards:
        recipients = card.learner.guardian_links.filter(receives_email=True).exclude(guardian__email="")
        if not recipients:
            skipped += 1
            continue
        pdf = render_cards([card])
        for link in recipients.select_related("guardian"):
            ok = _send(
                school,
                link.guardian.email,
                f"{school.name}: report card for {card.learner.full_name} ({card.term})",
                f"Dear {link.guardian.full_name},\n\n"
                f"Please find attached the report card for {card.learner.full_name}.\n\n{school.name}",
                "report_card",
                [(f"report-{card.serial}.pdf", pdf, "application/pdf")],
            )
            sent, failed = sent + ok, failed + (not ok)
    return {"sent": sent, "failed": failed, "no_email": skipped}
