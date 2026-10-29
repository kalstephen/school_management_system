from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("finance/categories", views.CategoryViewSet, basename="expense-category")
router.register("finance/sub-categories", views.SubCategoryViewSet, basename="expense-sub-category")
router.register("finance/suppliers", views.SupplierViewSet, basename="supplier")
router.register("finance/expenses", views.ExpenseViewSet, basename="expense")
router.register("finance/requisitions", views.RequisitionViewSet, basename="requisition")
router.register("finance/recurring", views.RecurringExpenseViewSet, basename="recurring-expense")
router.register("finance/petty-cash", views.PettyCashFloatViewSet, basename="petty-cash")
router.register("finance/budgets", views.BudgetViewSet, basename="budget")
router.register("finance/budget-lines", views.BudgetLineViewSet, basename="budget-line")
router.register("finance/purchase-orders", views.PurchaseOrderViewSet, basename="purchase-order")
router.register("finance/deliveries", views.DeliveryViewSet, basename="delivery")
router.register("finance/bills", views.SupplierBillViewSet, basename="supplier-bill")
router.register("finance/other-income", views.OtherIncomeViewSet, basename="other-income")

urlpatterns = [
    path("finance/settings/", views.FinanceSettingsView.as_view()),
    path("finance/reports/<slug:name>/", views.FinanceReportView.as_view()),
    *router.urls,
]
