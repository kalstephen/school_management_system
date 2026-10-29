from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("attendance/sessions", views.AttendanceSessionViewSet, basename="attendance-session")
router.register("attendance/records", views.AttendanceRecordViewSet, basename="attendance-record")

urlpatterns = [
    path("attendance/roll-call/", views.RollCallView.as_view()),
    path("attendance/summary/", views.AttendanceSummaryView.as_view()),
    path("attendance/register/", views.ClassRegisterView.as_view()),
    *router.urls,
]
