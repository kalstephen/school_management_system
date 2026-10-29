from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("discipline-cases", views.DisciplineCaseViewSet, basename="discipline-case")
router.register("sanctions", views.SanctionViewSet, basename="sanction")
router.register("counselling", views.CounsellingReferralViewSet, basename="counselling")
router.register("achievements", views.AchievementViewSet, basename="achievement")

urlpatterns = router.urls
