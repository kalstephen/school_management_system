from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("users", views.MembershipViewSet, basename="membership")
router.register("role-assignments", views.RoleAssignmentViewSet, basename="role-assignment")
router.register("permission-grants", views.PermissionGrantViewSet, basename="permission-grant")

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("auth/switch-school/", views.SwitchSchoolView.as_view()),
    path("auth/change-password/", views.ChangePasswordView.as_view()),
    path("roles/", views.RoleCatalogView.as_view()),
    *router.urls,
]
