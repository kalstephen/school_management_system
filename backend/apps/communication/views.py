import io

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.services import user_roles
from apps.core.permissions import has_perm
from apps.core.serializers import SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet

from .models import EmailLog, Notice, Notification
from .services import TEACHING_ROLES, publish_notice


class NoticeSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Notice
        fields = [
            "id",
            "title",
            "body",
            "audience",
            "roles",
            "pinned",
            "expires_on",
            "attachment",
            "email_guardians",
            "guardian_classes",
            "published_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["published_at"]


class NotificationSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "link", "read_at", "created_at"]


class EmailLogSerializer(SchoolOwnedSerializer):
    class Meta:
        model = EmailLog
        fields = ["id", "to", "subject", "kind", "status", "error", "created_at"]


class NoticeViewSet(SchoolViewSet):
    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer
    perms = {"read": "communication.view", "write": "communication.post"}
    action_perms = {"publish": "communication.post", "circular": "communication.view"}
    module = "communication"
    search_fields = ["title", "body"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if has_perm(self.request, "communication.post"):
            return queryset
        roles = set(user_roles(self.request.user, self.request.school).values_list("role", flat=True))
        visible = Q(audience=Notice.Audience.ALL_STAFF)
        if roles & TEACHING_ROLES:
            visible |= Q(audience=Notice.Audience.TEACHERS)
        ids = [n.id for n in queryset.filter(audience=Notice.Audience.ROLES) if roles & set(n.roles)]
        visible |= Q(pk__in=ids)
        today = timezone.localdate()
        return queryset.filter(visible, published_at__isnull=False).filter(
            Q(expires_on__isnull=True) | Q(expires_on__gte=today)
        )

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        return Response(publish_notice(self.get_object()))

    @action(detail=True, methods=["get"])
    def circular(self, request, pk=None):
        """Printable circular (PDF) on the school's letterhead."""
        notice = self.get_object()
        styles = getSampleStyleSheet()
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm
        )
        school = request.school
        story = [
            Paragraph(school.name.upper(), styles["Title"]),
            Paragraph(
                " · ".join(x for x in [school.address, school.phone, school.email] if x), styles["Normal"]
            ),
            Spacer(1, 8 * mm),
            Paragraph(f"<b>CIRCULAR: {notice.title}</b>", styles["Heading2"]),
            Paragraph((notice.published_at or notice.created_at).strftime("%d %B %Y"), styles["Normal"]),
            Spacer(1, 5 * mm),
        ]
        story += [Paragraph(p.replace("\n", "<br/>"), styles["BodyText"]) for p in notice.body.split("\n\n")]
        doc.build(story)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="circular-{notice.id}.pdf"'
        return response


class NotificationViewSet(SchoolViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    perms = {"read": "dashboard.view", "write": "dashboard.view"}
    http_method_names = ["get", "post"]
    filterset_fields = {"read_at": ["isnull"]}

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Notifications are created by the system."}, status=405)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        note = self.get_object()
        note.read_at = timezone.now()
        note.save()
        return Response(self.get_serializer(note).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated})


class EmailLogViewSet(SchoolViewSet):
    queryset = EmailLog.objects.all()
    serializer_class = EmailLogSerializer
    perms = {"read": "communication.post", "write": "communication.post"}
    http_method_names = ["get"]
    module = "communication"
    filterset_fields = ["status", "kind"]
