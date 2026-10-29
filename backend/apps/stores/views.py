import datetime

from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet
from apps.learners.services import learners_in

from .models import Asset, Item, Requirement, RequirementClearance, StockMovement, Store

PERMS = {"read": "stores.view", "write": "stores.manage"}
MODULE = "stores"


class StoreSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Store
        fields = ["id", "name", "keeper"]


class ItemSerializer(SchoolOwnedSerializer):
    store_name = LabelField("store.name")
    quantity = serializers.SerializerMethodField()
    below_reorder = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = ["id", "store", "store_name", "name", "unit", "reorder_level", "quantity", "below_reorder"]

    def get_quantity(self, obj):
        return float(obj.quantity)

    def get_below_reorder(self, obj):
        return obj.quantity <= obj.reorder_level


class StockMovementSerializer(SchoolOwnedSerializer):
    item_name = LabelField("item.name")

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "item",
            "item_name",
            "store",
            "kind",
            "quantity",
            "date",
            "reference",
            "issued_to",
            "notes",
        ]
        read_only_fields = ["store"]

    def validate(self, attrs):
        if attrs.get("kind") == "out" and attrs.get("quantity", 0) > attrs["item"].quantity:
            raise serializers.ValidationError(
                {"quantity": f"Only {attrs['item'].quantity} {attrs['item'].unit} in stock."}
            )
        if attrs.get("kind") != "adjust" and attrs.get("quantity", 0) <= 0:
            raise serializers.ValidationError({"quantity": "The quantity must be more than zero."})
        return attrs


class RequirementSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Requirement
        fields = ["id", "name", "item", "quantity_per_learner", "term", "section", "school_class"]


class ClearanceSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")

    class Meta:
        model = RequirementClearance
        fields = ["id", "requirement", "learner", "learner_name", "quantity_brought", "date"]


class AssetSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "tag",
            "category",
            "location",
            "condition",
            "purchase_date",
            "purchase_cost",
            "supplier",
            "custodian",
            "expense",
            "notes",
        ]


class StoreViewSet(SchoolViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    perms = PERMS
    module = MODULE


class ItemViewSet(SchoolViewSet):
    queryset = Item.objects.select_related("store")
    serializer_class = ItemSerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["store"]
    search_fields = ["name"]

    @action(detail=False, methods=["get"], url_path="reorder")
    def reorder(self, request):
        items = [i for i in self.get_queryset() if i.quantity <= i.reorder_level]
        return Response(self.get_serializer(items, many=True).data)


class StockMovementViewSet(SchoolViewSet):
    queryset = StockMovement.objects.select_related("item")
    serializer_class = StockMovementSerializer
    perms = PERMS
    module = MODULE
    http_method_names = ["get", "post"]
    filterset_fields = {"item": ["exact"], "store": ["exact"], "kind": ["exact"], "date": ["gte", "lte"]}

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, store=serializer.validated_data["item"].store)


class RequirementViewSet(SchoolViewSet):
    queryset = Requirement.objects.all()
    serializer_class = RequirementSerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["term", "section", "school_class"]

    def _learners(self, requirement):
        learners = learners_in(requirement.school, requirement.term, requirement.school_class)
        if requirement.section_id and not requirement.school_class_id:
            learners = learners.filter(
                enrolments__term=requirement.term, enrolments__school_class__section=requirement.section
            )
        return learners.distinct()

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """Who has cleared the requirement and who is still pending."""
        requirement = self.get_object()
        brought = {c.learner_id: c.quantity_brought for c in requirement.clearances.all()}
        rows = []
        for learner in self._learners(requirement).order_by("first_name"):
            qty = brought.get(learner.id, 0)
            rows.append(
                {
                    "learner": learner.id,
                    "name": learner.full_name,
                    "brought": float(qty),
                    "cleared": qty >= requirement.quantity_per_learner,
                }
            )
        return Response(
            {
                "requirement": str(requirement),
                "rows": rows,
                "cleared": sum(r["cleared"] for r in rows),
                "pending": sum(not r["cleared"] for r in rows),
            }
        )

    @action(detail=True, methods=["post"])
    def clear(self, request, pk=None):
        """Record what a learner brought; it is also added to stock when linked to an item."""
        requirement = self.get_object()
        learner = self._learners(requirement).filter(pk=request.data.get("learner")).first()
        if learner is None:
            raise BusinessRuleError({"learner": "This learner is not covered by the requirement."})
        qty = request.data.get("quantity", requirement.quantity_per_learner)
        clearance, _ = RequirementClearance.objects.update_or_create(
            school=request.school,
            requirement=requirement,
            learner=learner,
            defaults={"quantity_brought": qty, "date": request.data.get("date") or datetime.date.today()},
        )
        if requirement.item_id:
            StockMovement.objects.create(
                school=request.school,
                item=requirement.item,
                store=requirement.item.store,
                kind="in",
                quantity=qty,
                date=clearance.date,
                reference=f"Requirement: {requirement.name}",
                notes=learner.full_name,
            )
        return Response(ClearanceSerializer(clearance).data)


class ClearanceViewSet(SchoolViewSet):
    queryset = RequirementClearance.objects.select_related("learner")
    serializer_class = ClearanceSerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["requirement", "learner"]


class AssetViewSet(SchoolViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    perms = PERMS
    module = MODULE
    filterset_fields = ["category", "condition", "location"]
    search_fields = ["name", "tag", "location", "custodian"]
    export_title = "Asset register"
