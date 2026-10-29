import datetime

from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet, xlsx_response

from .models import Book, BookCopy, Loan

PERMS = {"read": "library.view", "write": "library.manage"}


class BookCopySerializer(SchoolOwnedSerializer):
    on_loan = serializers.BooleanField(source="is_on_loan", read_only=True)

    class Meta:
        model = BookCopy
        fields = ["id", "book", "barcode", "condition", "on_loan"]


class BookSerializer(SchoolOwnedSerializer):
    copies_total = serializers.SerializerMethodField()
    copies_available = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "isbn",
            "publisher",
            "year",
            "subject",
            "is_textbook",
            "shelf",
            "copies_total",
            "copies_available",
        ]

    def get_copies_total(self, obj):
        return obj.copies.exclude(condition="lost").count()

    def get_copies_available(self, obj):
        return obj.copies.exclude(condition="lost").exclude(loans__returned_on__isnull=True).count()


class LoanSerializer(SchoolOwnedSerializer):
    book_title = LabelField("copy.book.title")
    barcode = LabelField("copy.barcode")
    borrower = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Loan
        fields = [
            "id",
            "copy",
            "book_title",
            "barcode",
            "learner",
            "staff",
            "borrower",
            "issued_on",
            "due_on",
            "returned_on",
            "condition_on_return",
            "is_overdue",
        ]
        read_only_fields = ["returned_on", "condition_on_return"]

    def get_borrower(self, obj):
        return obj.learner.full_name if obj.learner else (obj.staff.full_name if obj.staff else "")

    def validate(self, attrs):
        if not attrs.get("learner") and not attrs.get("staff"):
            raise serializers.ValidationError({"learner": "Choose a learner or a staff member."})
        copy = attrs.get("copy")
        if copy and copy.is_on_loan:
            raise serializers.ValidationError({"copy": "This copy is already on loan."})
        if copy and copy.condition == BookCopy.Condition.LOST:
            raise serializers.ValidationError({"copy": "This copy is marked lost."})
        return attrs


class BookViewSet(SchoolViewSet):
    queryset = Book.objects.prefetch_related("copies")
    serializer_class = BookSerializer
    perms = PERMS
    module = "library"
    filterset_fields = ["subject", "is_textbook"]
    search_fields = ["title", "author", "isbn", "copies__barcode"]


class BookCopyViewSet(SchoolViewSet):
    queryset = BookCopy.objects.select_related("book")
    serializer_class = BookCopySerializer
    perms = PERMS
    module = "library"
    filterset_fields = ["book", "condition"]
    search_fields = ["barcode"]


class LoanViewSet(SchoolViewSet):
    queryset = Loan.objects.select_related("copy__book", "learner", "staff")
    serializer_class = LoanSerializer
    perms = PERMS
    module = "library"
    filterset_fields = {"learner": ["exact"], "staff": ["exact"], "returned_on": ["isnull"]}
    search_fields = ["copy__barcode", "copy__book__title", "learner__first_name", "learner__last_name"]

    @action(detail=True, methods=["post"], url_path="return")
    def return_book(self, request, pk=None):
        loan = self.get_object()
        if loan.returned_on:
            raise BusinessRuleError({"detail": "This book was already returned."})
        loan.returned_on = timezone.localdate()
        loan.condition_on_return = request.data.get("condition", "")
        loan.save()
        if loan.condition_on_return:
            loan.copy.condition = loan.condition_on_return
            loan.copy.save()
        return Response(self.get_serializer(loan).data)

    @action(detail=False, methods=["post"], url_path="issue-by-barcode")
    def issue_by_barcode(self, request):
        copy = BookCopy.objects.filter(school=request.school, barcode=request.data.get("barcode")).first()
        if copy is None:
            raise BusinessRuleError({"barcode": "No copy has this barcode."})
        days = int(request.data.get("days", 14))
        serializer = self.get_serializer(
            data={
                "copy": copy.id,
                "learner": request.data.get("learner"),
                "staff": request.data.get("staff"),
                "issued_on": timezone.localdate(),
                "due_on": timezone.localdate() + datetime.timedelta(days=days),
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(school=request.school)
        return Response(serializer.data, status=201)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        rows = self.get_queryset().filter(returned_on__isnull=True, due_on__lt=timezone.localdate())
        data = self.get_serializer(rows, many=True).data
        if request.query_params.get("download") == "xlsx":
            return xlsx_response("Overdue books", [dict(r) for r in data])
        return Response(data)
