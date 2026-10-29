from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("platform/plans", views.PlanViewSet, basename="plan")
router.register("platform/schools", views.PlatformSchoolViewSet, basename="platform-school")
router.register("platform/team", views.PlatformTeamViewSet, basename="platform-team")
router.register("platform/users", views.PlatformUserViewSet, basename="platform-user")
router.register("support-access", views.SupportAccessViewSet, basename="support-access")
router.register("platform/requests", views.AccessRequestViewSet, basename="access-request")

urlpatterns = [
    path("addons/", views.SchoolAddonsView.as_view()),
    path("access-status/", views.AccessStatusView.as_view()),
    path("platform/overview/", views.PlatformOverviewView.as_view()),
    path("modules/", views.ModuleCatalogView.as_view()),
    path("public/access-requests/", views.PublicAccessRequestView.as_view()),
    *router.urls,
]
