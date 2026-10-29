from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("stores/stores", views.StoreViewSet, basename="store")
router.register("stores/items", views.ItemViewSet, basename="item")
router.register("stores/movements", views.StockMovementViewSet, basename="stock-movement")
router.register("stores/requirements", views.RequirementViewSet, basename="requirement")
router.register("stores/clearances", views.ClearanceViewSet, basename="clearance")
router.register("stores/assets", views.AssetViewSet, basename="asset")

urlpatterns = router.urls
