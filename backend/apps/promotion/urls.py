from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("promotion-rules", views.PromotionRuleViewSet, basename="promotion-rule")
router.register("promotion-batches", views.PromotionBatchViewSet, basename="promotion-batch")

urlpatterns = router.urls
