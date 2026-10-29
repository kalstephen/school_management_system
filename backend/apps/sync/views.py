from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import SchoolPermission

from .models import SyncOp
from .services import Reject, apply_ops, resolve


class SyncView(APIView):
    """POST {"ops": [{"op_id": uuid, "kind": "attendance"|"mark", "payload": {...}, "base_version": n}]}"""

    permission_classes = [IsAuthenticated, SchoolPermission]

    def get_required_perm(self, request):
        return "dashboard.view"

    def post(self, request):
        ops = request.data.get("ops", [])
        if not isinstance(ops, list) or len(ops) > 2000:
            raise BusinessRuleError({"ops": "Send a list of at most 2000 changes."})
        return Response({"results": apply_ops(request.school, request.user, ops)})


class ConflictsView(APIView):
    permission_classes = [IsAuthenticated, SchoolPermission]

    def get_required_perm(self, request):
        return "dashboard.view"

    def get(self, request):
        rows = SyncOp.objects.filter(school=request.school, user=request.user, status=SyncOp.Status.CONFLICT)
        return Response(
            [
                {
                    "id": r.id,
                    "op_id": str(r.op_id),
                    "kind": r.kind,
                    "payload": r.payload,
                    "server_value": r.server_value,
                    "detail": r.detail,
                    "created_at": r.created_at,
                }
                for r in rows
            ]
        )

    def post(self, request):
        op = SyncOp.objects.filter(
            school=request.school, user=request.user, pk=request.data.get("id")
        ).first()
        if op is None:
            raise BusinessRuleError({"id": "Unknown conflict."})
        try:
            resolve(op, request.data.get("keep", "server"))
        except Reject as exc:
            raise BusinessRuleError({"detail": str(exc)})
        return Response({"status": op.status, "detail": op.detail})
