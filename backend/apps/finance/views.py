import datetime

from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import SchoolPermission, has_perm
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet, xlsx_response
from apps.schoolsetup.models import Term, current_term

from . import reports, services
from .models import (
    Approval,
    Budget,
    BudgetLine,
    Delivery,
    Expense,
    ExpenseCategory,
    ExpenseSubCategory,
    FinanceSettings,
    OtherIncome,
    PettyCashCount,
    PettyCashEntry,
    PettyCashFloat,
    PurchaseOrder,
    RecurringExpense,
    Requisition,
    Supplier,
    SupplierBill,
    SupplierPayment,
)

PERMS = {"read": "finance.view", "write": "finance.manage"}
MODULE = "finance"


# ---------- serializers ----------


class SubCategorySerializer(SchoolOwnedSerializer):
    class Meta:
        model = ExpenseSubCategory
        fields = ["id", "category", "name"]


class CategorySerializer(SchoolOwnedSerializer):
    """A spending category with its sub-categories. `sub_category_names` sets the list in one
    go: new names are added, missing ones removed (unless expenses already use them)."""

    sub_categories = SubCategorySerializer(many=True, read_only=True)
    sub_category_names = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=True), write_only=True, required=False
    )
    expenses = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_capital", "order", "sub_categories", "sub_category_names", "expenses"]

    def get_expenses(self, obj):
        return obj.expenses.count()

    def validate_name(self, value):
        value = value.strip()
        school = self.context["request"].school
        clash = ExpenseCategory.objects.filter(school=school, name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("There is already a category with this name.")
        return value

    def validate_sub_category_names(self, value):
        names = [n.strip() for n in value if n.strip()]
        if len({n.lower() for n in names}) != len(names):
            raise serializers.ValidationError("Each sub-category name must be different.")
        if self.instance:
            wanted = {n.lower() for n in names}
            in_use = [
                s.name
                for s in self.instance.sub_categories.all()
                if s.name.lower() not in wanted and Expense.objects.filter(sub_category=s).exists()
            ]
            if in_use:
                raise serializers.ValidationError(
                    f"Expenses use {', '.join(in_use)}, so it cannot be removed. Move those expenses first."
                )
        return names

    def create(self, validated_data):
        names = validated_data.pop("sub_category_names", [])
        category = super().create(validated_data)
        self._set_subs(category, names)
        return category

    def update(self, instance, validated_data):
        names = validated_data.pop("sub_category_names", None)
        category = super().update(instance, validated_data)
        if names is not None:
            self._set_subs(category, names)
        return category

    def _set_subs(self, category, names):
        wanted = {n.lower(): n for n in names}
        for sub in category.sub_categories.all():
            if wanted.pop(sub.name.lower(), None) is None:
                sub.delete()
        for name in wanted.values():
            ExpenseSubCategory.objects.create(school=category.school, category=category, name=name)


class SupplierSerializer(SchoolOwnedSerializer):
    amount_owed = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = ["id", "name", "contact_person", "phone", "email", "address", "tin", "amount_owed"]

    def get_amount_owed(self, obj):
        return float(sum(b.balance for b in obj.bills.exclude(status="paid")))


class ApprovalSerializer(SchoolOwnedSerializer):
    user_name = LabelField("user.display_name", default=None)

    class Meta:
        model = Approval
        fields = ["id", "user", "user_name", "level", "decision", "comment", "created_at"]


class ExpenseSerializer(SchoolOwnedSerializer):
    category_name = LabelField("category.name")
    sub_category_name = LabelField("sub_category.name", default=None)
    supplier_name = LabelField("supplier.name", default=None)
    term_label = LabelField("term", default=None)
    approvals = ApprovalSerializer(many=True, read_only=True)
    entered_by = LabelField("created_by.display_name", default=None)

    class Meta:
        model = Expense
        fields = [
            "id",
            "date",
            "category",
            "category_name",
            "sub_category",
            "sub_category_name",
            "description",
            "amount",
            "method",
            "payee",
            "supplier",
            "supplier_name",
            "reference",
            "receipt",
            "department",
            "section",
            "school_class",
            "project",
            "term",
            "term_label",
            "period_override_reason",
            "status",
            "required_level",
            "requisition",
            "paid_on",
            "approvals",
            "entered_by",
            "created_at",
        ]
        read_only_fields = ["status", "required_level", "paid_on"]

    def validate(self, attrs):
        if attrs.get("amount") is not None and attrs["amount"] <= 0:
            raise serializers.ValidationError({"amount": "The amount must be more than zero."})
        sub = attrs.get("sub_category")
        category = attrs.get("category", getattr(self.instance, "category", None))
        if sub and category and sub.category_id != category.id:
            raise serializers.ValidationError(
                {"sub_category": "The sub-category must belong to the category."}
            )
        if attrs.get("term") and not attrs.get(
            "period_override_reason", getattr(self.instance, "period_override_reason", "")
        ):
            attrs.pop("term")
        return attrs


class RequisitionSerializer(SchoolOwnedSerializer):
    department_name = LabelField("department.name", default=None)
    requested_by = LabelField("created_by.display_name", default=None)
    status_label = LabelField("get_status_display")
    steps = serializers.SerializerMethodField()
    waiting_for = serializers.SerializerMethodField()
    can_act = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Requisition
        fields = [
            "id",
            "department",
            "department_name",
            "title",
            "details",
            "items",
            "estimated_amount",
            "needed_by",
            "status",
            "status_label",
            "decided_by",
            "decision_comment",
            "requested_by",
            "created_at",
            "steps",
            "waiting_for",
            "can_act",
            "is_mine",
            "disbursed_amount",
            "disbursement_method",
            "disbursed_at",
            "spent_amount",
            "returned_amount",
            "accountability_note",
            "receipt",
            "accounted_submitted_at",
            "accounted_at",
        ]
        read_only_fields = [
            f
            for f in fields
            if f not in ("department", "title", "details", "items", "estimated_amount", "needed_by")
        ]

    def get_steps(self, obj):
        """Every step with its state: done (who, when, comment), current, or to come."""
        from .requisitions import STEPS

        decisions = {a.step: a for a in obj.approvals.select_related("user") if a.step}
        rows = []
        for index, step in enumerate(obj.route or []):
            decision = decisions.get(step)
            state = "done" if index < obj.step else "current" if index == obj.step else "todo"
            if step == "finance" and obj.disbursed_at:
                state = "done"
            if obj.status == Requisition.Status.REJECTED and decision and decision.decision == "rejected":
                state = "rejected"
            rows.append(
                {
                    "step": step,
                    "label": STEPS.get(step, step),
                    "state": state,
                    "by": (decision.user.display_name if decision and decision.user else None)
                    if step != "finance"
                    else (obj.disbursed_by.display_name if obj.disbursed_by else None),
                    "at": decision.created_at
                    if decision
                    else obj.disbursed_at
                    if step == "finance"
                    else None,
                    "comment": decision.comment if decision else "",
                }
            )
        return rows

    def get_waiting_for(self, obj):
        from .requisitions import STEPS, current_step

        if obj.status == Requisition.Status.DISBURSED:
            return (
                "Finance to confirm the accounts"
                if obj.accounted_submitted_at
                else "The requester to account"
            )
        if obj.status not in (Requisition.Status.PENDING, Requisition.Status.APPROVED):
            return None
        step = current_step(obj)
        return STEPS.get(step, step) if step else None

    def get_can_act(self, obj):
        from .requisitions import can_act

        request = self.context.get("request")
        return bool(request and can_act(request.user, obj))

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and obj.created_by_id == request.user.pk)


class RecurringExpenseSerializer(SchoolOwnedSerializer):
    class Meta:
        model = RecurringExpense
        fields = [
            "id",
            "category",
            "sub_category",
            "description",
            "amount",
            "method",
            "payee",
            "supplier",
            "frequency",
            "next_date",
            "is_active",
        ]


class PettyCashFloatSerializer(SchoolOwnedSerializer):
    balance = serializers.SerializerMethodField()
    needs_replenishment = serializers.SerializerMethodField()
    custodian_name = LabelField("custodian.display_name")

    class Meta:
        model = PettyCashFloat
        fields = [
            "id",
            "name",
            "custodian",
            "custodian_name",
            "float_amount",
            "replenish_below",
            "is_active",
            "balance",
            "needs_replenishment",
        ]

    def get_balance(self, obj):
        return float(obj.balance)

    def get_needs_replenishment(self, obj):
        return services.needs_replenishment(obj)


class PettyCashEntrySerializer(SchoolOwnedSerializer):
    class Meta:
        model = PettyCashEntry
        fields = ["id", "float", "date", "kind", "amount", "description", "expense"]
        read_only_fields = ["expense"]


class PettyCashCountSerializer(SchoolOwnedSerializer):
    difference = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = PettyCashCount
        fields = ["id", "float", "date", "expected", "counted", "difference", "notes"]
        read_only_fields = ["expected"]


class BudgetLineSerializer(SchoolOwnedSerializer):
    category_name = LabelField("category.name")

    class Meta:
        model = BudgetLine
        fields = ["id", "budget", "category", "category_name", "amount"]


class BudgetSerializer(SchoolOwnedSerializer):
    lines = BudgetLineSerializer(many=True, read_only=True)
    term_label = LabelField("term")

    class Meta:
        model = Budget
        fields = ["id", "term", "term_label", "notes", "is_approved", "lines"]


class PurchaseOrderSerializer(SchoolOwnedSerializer):
    supplier_name = LabelField("supplier.name")
    total = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = ["id", "supplier", "supplier_name", "number", "date", "items", "status", "notes", "total"]

    def get_total(self, obj):
        return float(obj.total)


class DeliverySerializer(SchoolOwnedSerializer):
    class Meta:
        model = Delivery
        fields = ["id", "purchase_order", "date", "items", "received_by", "notes"]


class SupplierPaymentSerializer(SchoolOwnedSerializer):
    class Meta:
        model = SupplierPayment
        fields = ["id", "bill", "date", "amount", "method", "reference", "expense"]
        read_only_fields = ["expense"]


class SupplierBillSerializer(SchoolOwnedSerializer):
    supplier_name = LabelField("supplier.name")
    paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    payments = SupplierPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierBill
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "purchase_order",
            "category",
            "reference",
            "description",
            "date",
            "due_date",
            "amount",
            "status",
            "paid",
            "balance",
            "payments",
        ]
        read_only_fields = ["status"]

    def get_paid(self, obj):
        return float(obj.paid)

    def get_balance(self, obj):
        return float(obj.balance)


class OtherIncomeSerializer(SchoolOwnedSerializer):
    term_label = LabelField("term", default=None)

    class Meta:
        model = OtherIncome
        fields = [
            "id",
            "date",
            "source",
            "description",
            "amount",
            "received_from",
            "method",
            "reference",
            "term",
            "term_label",
        ]
        read_only_fields = ["term"]


class FinanceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceSettings
        fields = ["bursar_limit", "head_limit"]

    def validate(self, attrs):
        if attrs.get("bursar_limit", 0) > attrs.get(
            "head_limit", self.instance.head_limit if self.instance else 0
        ):
            raise serializers.ValidationError(
                {"head_limit": "The head teacher's limit must be above the bursar's."}
            )
        return attrs


# ---------- viewsets ----------


class CategoryViewSet(SchoolViewSet):
    queryset = ExpenseCategory.objects.prefetch_related("sub_categories")
    serializer_class = CategorySerializer
    perms = {"read": "finance.request", "write": "finance.manage"}
    module = MODULE

    def get_required_perm(self, request):
        if request.method == "GET" and has_perm(request, "finance.view"):
            return "finance.view"
        return super().get_required_perm(request)

    def perform_destroy(self, instance):
        used = instance.expenses.count()
        if used:
            raise BusinessRuleError(
                {"detail": f"{used} expense(s) use {instance.name}. Move them to another category first."}
            )
        instance.delete()


class SubCategoryViewSet(SchoolViewSet):
    queryset = ExpenseSubCategory.objects.all()
    serializer_class = SubCategorySerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["category"]


class SupplierViewSet(SchoolViewSet):
    queryset = Supplier.objects.prefetch_related("bills")
    serializer_class = SupplierSerializer
    perms = PERMS
    module = MODULE
    search_fields = ["name", "phone", "tin", "contact_person"]

    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        return Response(reports.supplier_statement(self.get_object()))


class ExpenseViewSet(SchoolViewSet):
    queryset = Expense.objects.select_related(
        "category", "sub_category", "supplier", "term__academic_year", "created_by"
    ).prefetch_related("approvals__user")
    serializer_class = ExpenseSerializer
    perms = PERMS
    action_perms = {
        "submit": "finance.manage",
        "approve": "finance.approve",
        "reject": "finance.approve",
        "pay": "finance.manage",
        "bulk": "finance.manage",
        "import_csv": "finance.manage",
        "generate_recurring": "finance.manage",
    }
    module = MODULE
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = {
        "date": ["exact", "gte", "lte"],
        "category": ["exact"],
        "sub_category": ["exact"],
        "status": ["exact", "in"],
        "method": ["exact"],
        "supplier": ["exact"],
        "term": ["exact"],
        "department": ["exact"],
        "project": ["exact"],
    }
    search_fields = ["description", "payee", "reference", "project"]
    ordering_fields = ["date", "amount", "created_at"]
    export_title = "Expenses"

    def perform_update(self, serializer):
        if serializer.instance.status not in (Expense.Status.DRAFT, Expense.Status.REJECTED):
            raise BusinessRuleError({"detail": "Submitted or approved expenses cannot be edited."})
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status not in (Expense.Status.DRAFT, Expense.Status.REJECTED):
            raise BusinessRuleError({"detail": "Only draft or rejected expenses can be deleted."})
        instance.delete()

    def _fresh(self, expense):
        """Re-read after a workflow step so the response shows the new approval trail."""
        return Response(self.get_serializer(self.get_queryset().get(pk=expense.pk)).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self._fresh(services.submit_expense(self.get_object(), request.user))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._fresh(
            services.approve_expense(self.get_object(), request.user, request.data.get("comment", ""))
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._fresh(
            services.reject_expense(self.get_object(), request.user, request.data.get("comment", ""))
        )

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        return self._fresh(
            services.mark_paid(
                self.get_object(),
                request.data.get("paid_on"),
                request.data.get("method"),
                request.data.get("reference"),
            )
        )

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        """Daily cash sheet: many expense lines in one go, each submitted for approval."""
        created, errors = [], []
        for index, row in enumerate(request.data.get("rows", [])):
            serializer = self.get_serializer(data=row)
            if serializer.is_valid():
                expense = serializer.save(school=request.school)
                if request.data.get("submit", True):
                    services.submit_expense(expense, request.user)
                created.append(expense.id)
            else:
                errors.append({"row": index + 1, "errors": serializer.errors})
        return Response({"created": len(created), "errors": errors})

    @action(detail=False, methods=["post"], url_path="import", parser_classes=[MultiPartParser, FormParser])
    def import_csv(self, request):
        """Import past expenses from CSV.

        Columns: date, category, sub_category, description, amount, method, payee, reference."""
        import csv
        import io

        upload = request.FILES.get("file")
        if upload is None:
            raise BusinessRuleError({"file": "Attach a CSV file."})
        reader = csv.DictReader(io.StringIO(upload.read().decode("utf-8-sig")))
        categories = {c.name.lower(): c for c in ExpenseCategory.objects.filter(school=request.school)}
        created, errors = 0, []
        for line, row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            category = categories.get(row.get("category", "").lower())
            try:
                if category is None:
                    raise ValueError(f"unknown category '{row.get('category')}'")
                date = datetime.date.fromisoformat(row.get("date", ""))
                amount = int(float(row.get("amount", "0").replace(",", "")))
                if amount <= 0:
                    raise ValueError("amount must be more than zero")
            except ValueError as exc:
                errors.append({"row": line, "error": str(exc)})
                continue
            sub = category.sub_categories.filter(name__iexact=row.get("sub_category", "")).first()
            method = row.get("method", "cash").lower().replace(" ", "_")
            Expense.objects.create(
                school=request.school,
                date=date,
                category=category,
                sub_category=sub,
                description=row.get("description") or category.name,
                amount=amount,
                method=method if method in dict(Expense._meta.get_field("method").choices) else "cash",
                payee=row.get("payee", ""),
                reference=row.get("reference", ""),
                status=Expense.Status.PAID,
                paid_on=date,
            )
            created += 1
        return Response({"created": created, "errors": errors})

    @action(detail=False, methods=["post"], url_path="generate-recurring")
    def generate_recurring(self, request):
        return Response({"created": services.generate_recurring(request.school)})

    @action(detail=False, methods=["get"], url_path="awaiting-me")
    def awaiting_me(self, request):
        from apps.accounts.services import approval_level

        level = approval_level(request.user, request.school)
        rows = self.get_queryset().filter(status=Expense.Status.PENDING, required_level__lte=level)
        return Response(self.get_serializer(rows, many=True).data)


class RequisitionViewSet(SchoolViewSet):
    """Requisitions: ask, approve up the ranks, finance issues the money, the requester
    accounts for it. Everyone sees their own; approvers see what waits for them (?waiting=1)
    and what they decided; finance sees all."""

    queryset = Requisition.objects.select_related(
        "department", "created_by", "disbursed_by"
    ).prefetch_related("approvals__user")
    serializer_class = RequisitionSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    perms = {"read": "finance.request", "write": "finance.request"}
    action_perms = {
        "approve": "finance.request",
        "reject": "finance.request",
        "disburse": "finance.manage",
        "account": "finance.request",
        "confirm": "finance.manage",
    }
    module = MODULE
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["status", "department"]

    def get_queryset(self):
        from django.db.models import Q

        from .requisitions import can_act

        queryset = super().get_queryset()
        user = self.request.user
        if self.request.query_params.get("waiting"):
            open_ = queryset.filter(status__in=[Requisition.Status.PENDING, Requisition.Status.APPROVED])
            return queryset.filter(pk__in=[r.pk for r in open_ if can_act(user, r)])
        if self.request.query_params.get("mine"):
            return queryset.filter(created_by=user)
        if has_perm(self.request, "finance.view"):
            return queryset
        open_ = queryset.filter(status__in=[Requisition.Status.PENDING, Requisition.Status.APPROVED])
        waiting = [r.pk for r in open_ if can_act(user, r)]
        return queryset.filter(Q(created_by=user) | Q(approvals__user=user) | Q(pk__in=waiting)).distinct()

    def perform_create(self, serializer):
        from .requisitions import submit

        requisition = serializer.save(school=self.request.school)
        submit(requisition, self.request.user)

    def perform_update(self, serializer):
        requisition = serializer.instance
        if requisition.created_by_id != self.request.user.pk or requisition.approvals.exists():
            raise BusinessRuleError(
                {"detail": "A requisition can be changed only by its requester, before anyone decides."}
            )
        serializer.save()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        from . import requisitions

        requisition = requisitions.approve(self.get_object(), request.user, request.data.get("comment", ""))
        return Response(self.get_serializer(requisition).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        from . import requisitions

        requisition = requisitions.reject(self.get_object(), request.user, request.data.get("comment", ""))
        return Response(self.get_serializer(requisition).data)

    @action(detail=True, methods=["post"])
    def disburse(self, request, pk=None):
        """Finance issues the money: {amount, method, category, sub_category}."""
        from decimal import Decimal, InvalidOperation

        from . import requisitions

        requisition = self.get_object()
        category = ExpenseCategory.objects.filter(
            school=request.school, pk=request.data.get("category")
        ).first()
        if category is None:
            raise BusinessRuleError({"category": "Choose the expense category."})
        sub = (
            category.sub_categories.filter(pk=request.data.get("sub_category")).first()
            if request.data.get("sub_category")
            else None
        )
        try:
            amount = Decimal(str(request.data.get("amount") or requisition.estimated_amount))
        except InvalidOperation:
            raise BusinessRuleError({"amount": "The amount must be a number."})
        requisition = requisitions.disburse(
            requisition, request.user, amount, request.data.get("method"), category, sub
        )
        return Response(self.get_serializer(requisition).data)

    @action(detail=True, methods=["post"])
    def account(self, request, pk=None):
        """The requester reports how the money was used: {spent_amount, returned_amount,
        accountability_note, receipt (file)}."""
        from decimal import Decimal, InvalidOperation

        from . import requisitions

        def money(key):
            value = request.data.get(key)
            if value in (None, ""):
                return None
            try:
                return Decimal(str(value))
            except InvalidOperation:
                raise BusinessRuleError({key: "Must be a number."})

        requisition = requisitions.account(
            self.get_object(),
            request.user,
            money("spent_amount"),
            money("returned_amount"),
            request.data.get("accountability_note", ""),
            request.FILES.get("receipt"),
        )
        return Response(self.get_serializer(requisition).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        from . import requisitions

        return Response(
            self.get_serializer(requisitions.confirm_accountability(self.get_object(), request.user)).data
        )


class RecurringExpenseViewSet(SchoolViewSet):
    queryset = RecurringExpense.objects.all()
    serializer_class = RecurringExpenseSerializer
    perms = PERMS
    module = MODULE


class PettyCashFloatViewSet(SchoolViewSet):
    queryset = PettyCashFloat.objects.select_related("custodian")
    serializer_class = PettyCashFloatSerializer
    perms = PERMS
    action_perms = {
        "spend": "finance.manage",
        "topup": "finance.manage",
        "book": "finance.view",
        "count": "finance.manage",
    }
    module = MODULE

    @action(detail=True, methods=["post"])
    def topup(self, request, pk=None):
        petty = self.get_object()
        entry = PettyCashEntry.objects.create(
            school=request.school,
            float=petty,
            date=request.data.get("date") or datetime.date.today(),
            kind="topup",
            amount=request.data.get("amount"),
            description=request.data.get("description") or "Top-up",
        )
        return Response(PettyCashEntrySerializer(entry).data)

    @action(detail=True, methods=["post"])
    def spend(self, request, pk=None):
        petty = self.get_object()
        category = ExpenseCategory.objects.filter(
            school=request.school, pk=request.data.get("category")
        ).first()
        if category is None:
            raise BusinessRuleError({"category": "Choose an expense category."})
        sub = ExpenseSubCategory.objects.filter(
            school=request.school, pk=request.data.get("sub_category")
        ).first()
        entry = services.spend_petty_cash(
            petty,
            request.user,
            request.data.get("date") or datetime.date.today(),
            request.data.get("amount", 0),
            request.data.get("description", ""),
            category,
            sub,
            request.data.get("payee", ""),
        )
        return Response(PettyCashEntrySerializer(entry).data)

    @action(detail=True, methods=["get", "post"])
    def count(self, request, pk=None):
        petty = self.get_object()
        if request.method == "POST":
            record = PettyCashCount.objects.create(
                school=request.school,
                float=petty,
                date=request.data.get("date") or datetime.date.today(),
                expected=petty.balance,
                counted=request.data.get("counted"),
                notes=request.data.get("notes", ""),
            )
            return Response(PettyCashCountSerializer(record).data)
        return Response(PettyCashCountSerializer(petty.counts.order_by("-date")[:30], many=True).data)

    @action(detail=True, methods=["get"])
    def book(self, request, pk=None):
        params = request.query_params
        start = datetime.date.fromisoformat(params["start"]) if params.get("start") else None
        end = datetime.date.fromisoformat(params["end"]) if params.get("end") else None
        data = reports.petty_cash_book(self.get_object(), start, end)
        if params.get("download") == "xlsx":
            return xlsx_response("Petty cash book", data["rows"])
        return Response(data)


class BudgetViewSet(SchoolViewSet):
    queryset = Budget.objects.prefetch_related("lines__category").select_related("term__academic_year")
    serializer_class = BudgetSerializer
    perms = PERMS
    action_perms = {
        "approve": "finance.approve",
        "copy_forward": "finance.manage",
        "set_lines": "finance.manage",
    }
    module = MODULE
    filterset_fields = ["term"]

    @action(detail=True, methods=["post"], url_path="copy-forward")
    def copy_forward(self, request, pk=None):
        budget = self.get_object()
        source = Budget.objects.filter(school=request.school, pk=request.data.get("from_budget")).first()
        if source is None:
            source = (
                Budget.objects.filter(school=request.school, term__start_date__lt=budget.term.start_date)
                .order_by("-term__start_date")
                .first()
            )
        if source is None:
            raise BusinessRuleError({"detail": "There is no earlier budget to copy."})
        return Response({"copied": services.copy_budget_forward(budget, source)})

    @action(detail=True, methods=["post"], url_path="set-lines")
    def set_lines(self, request, pk=None):
        budget = self.get_object()
        if budget.is_approved and not has_perm(request, "finance.approve"):
            raise BusinessRuleError({"detail": "The budget is approved; only an approver can change it."})
        for row in request.data.get("lines", []):
            category = ExpenseCategory.objects.filter(school=request.school, pk=row.get("category")).first()
            if category:
                BudgetLine.objects.update_or_create(
                    school=request.school,
                    budget=budget,
                    category=category,
                    defaults={"amount": row.get("amount") or 0},
                )
        return Response(self.get_serializer(Budget.objects.get(pk=budget.pk)).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        budget = self.get_object()
        budget.is_approved = True
        budget.save()
        return Response(self.get_serializer(budget).data)


class BudgetLineViewSet(SchoolViewSet):
    queryset = BudgetLine.objects.select_related("category")
    serializer_class = BudgetLineSerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["budget"]


class PurchaseOrderViewSet(SchoolViewSet):
    queryset = PurchaseOrder.objects.select_related("supplier")
    serializer_class = PurchaseOrderSerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["supplier", "status"]
    search_fields = ["number", "supplier__name"]


class DeliveryViewSet(SchoolViewSet):
    queryset = Delivery.objects.all()
    serializer_class = DeliverySerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["purchase_order"]

    def perform_create(self, serializer):
        delivery = serializer.save(school=self.request.school)
        services.receive_delivery(delivery)
        po = delivery.purchase_order
        po.status = (
            PurchaseOrder.Status.RECEIVED
            if self.request.data.get("complete")
            else PurchaseOrder.Status.PARTLY_RECEIVED
        )
        po.save()


class SupplierBillViewSet(SchoolViewSet):
    queryset = SupplierBill.objects.select_related("supplier").prefetch_related("payments")
    serializer_class = SupplierBillSerializer
    perms = PERMS
    action_perms = {"pay": "finance.approve"}
    module = MODULE
    filterset_fields = ["supplier", "status"]

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        payment = services.pay_bill(
            self.get_object(),
            request.data.get("date") or datetime.date.today(),
            request.data.get("amount", 0),
            request.data.get("method", "bank"),
            request.data.get("reference", ""),
        )
        return Response(SupplierPaymentSerializer(payment).data)


class OtherIncomeViewSet(SchoolViewSet):
    queryset = OtherIncome.objects.select_related("term__academic_year")
    serializer_class = OtherIncomeSerializer
    perms = PERMS
    module = MODULE
    filterset_fields = {"date": ["gte", "lte"], "source": ["exact"], "term": ["exact"]}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.school.other_income_enabled:
            raise BusinessRuleError({"detail": "Other income is switched off for this school."})


class FinanceSettingsView(APIView):
    permission_classes = [IsAuthenticated, SchoolPermission]
    module = MODULE

    def get_required_perm(self, request):
        return "finance.view" if request.method == "GET" else "finance.approve"

    def get(self, request):
        return Response(FinanceSettingsSerializer(FinanceSettings.for_school(request.school)).data)

    def patch(self, request):
        serializer = FinanceSettingsSerializer(
            FinanceSettings.for_school(request.school), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class FinanceReportView(APIView):
    """GET /api/finance/reports/<name>/?term=&date=&start=&download=xlsx"""

    permission_classes = [IsAuthenticated, SchoolPermission]
    module = MODULE

    def get_required_perm(self, request):
        return "finance.view"

    def get(self, request, name):
        params = request.query_params
        school = request.school
        term = Term.objects.filter(school=school, pk=params.get("term")).first() or current_term(school)
        if name == "daily":
            date = (
                datetime.date.fromisoformat(params["date"]) if params.get("date") else datetime.date.today()
            )
            data, rows = reports.daily_sheet(school, date), None
            rows = data["items"]
        elif name == "weekly":
            start = (
                datetime.date.fromisoformat(params["start"])
                if params.get("start")
                else (datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday()))
            )
            data = reports.weekly_summary(school, start)
            rows = data["rows"]
        elif term is None:
            raise BusinessRuleError({"term": "No term is set up yet."})
        elif name == "termly":
            data = reports.termly_statement(school, term)
            rows = [{"category": c["category"], "total": c["total"]} for c in data["categories"]]
        elif name == "budget-vs-actual":
            data = reports.budget_vs_actual(school, term)
            rows = data["lines"]
        elif name == "top-items":
            data = {"term": str(term), "rows": reports.top_cost_items(school, term)}
            rows = data["rows"]
        elif name == "compare-last-year":
            data = reports.same_term_last_year(school, term)
            rows = data["rows"]
        elif name == "outstanding-bills":
            data = {"rows": reports.outstanding_bills(school)}
            rows = data["rows"]
        else:
            raise BusinessRuleError({"detail": f"Unknown report '{name}'."})
        if params.get("download") == "xlsx":
            return xlsx_response(name.replace("-", " ").title(), rows or [])
        return Response(data)
