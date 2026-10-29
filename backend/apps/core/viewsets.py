import io

from django.http import HttpResponse
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Font
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated

from .permissions import SchoolPermission


def _cell(value):
    if isinstance(value, (list, dict)):
        return str(value)
    return value


def xlsx_response(title, rows):
    """Build an Excel download from a list of dicts."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31] or "Export"
    if rows:
        headers = list(rows[0].keys())
        sheet.append([h.replace("_", " ").title() for h in headers])
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append([_cell(row.get(h)) for h in headers])
    buffer = io.BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{slugify(title) or "export"}.xlsx"'
    return response


class SchoolScopedMixin:
    """Common behaviour for every school API view.

    Subclasses set:
      module        – module key; requests are refused when it is switched off
      perms         – {"read": perm, "write": perm}
      action_perms  – per-action overrides, e.g. {"approve": "finance.approve"}
    """

    module = None
    perms = {}
    action_perms = {}
    permission_classes = [IsAuthenticated, SchoolPermission]

    def get_required_perm(self, request):
        action_name = getattr(self, "action", None)
        if action_name in self.action_perms:
            return self.action_perms[action_name]
        if request.method in SAFE_METHODS:
            return self.perms.get("read")
        return self.perms.get("write")

    def get_queryset(self):
        return super().get_queryset().filter(school=self.request.school)


class SchoolViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    export_title = None

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Excel export of the current list, with the same filters and search applied."""
        queryset = self.filter_queryset(self.get_queryset())
        data = self.get_serializer(queryset, many=True).data
        title = self.export_title or self.get_queryset().model._meta.verbose_name_plural.title()
        return xlsx_response(str(title), [dict(row) for row in data])


class SchoolReadOnlyViewSet(SchoolScopedMixin, viewsets.ReadOnlyModelViewSet):
    pass
