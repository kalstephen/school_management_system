from django.urls import path
from rest_framework.routers import DefaultRouter

from . import history, views

router = DefaultRouter()
router.register("audit-log", views.AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view()),
    path("analytics/", views.AnalyticsView.as_view()),
    path("analytics/history/", history.HistoryView.as_view()),
    path("analytics/history/learner/<int:pk>/", history.LearnerHistoryView.as_view()),
    path("attendance/chronic/", views.ChronicAbsenceView.as_view()),
    *router.urls,
]
