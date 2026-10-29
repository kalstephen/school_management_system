from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("exams", views.ExamViewSet, basename="exam")
router.register("exam-schedule", views.ExamScheduleViewSet, basename="exam-schedule")
router.register("mark-sheets", views.MarkSheetViewSet, basename="mark-sheet")
router.register("aoi-scores", views.AOIScoreViewSet, basename="aoi-score")
router.register("nursery-ratings", views.NurseryRatingViewSet, basename="nursery-rating")
router.register("results", views.ResultSummaryViewSet, basename="result")
router.register("report-cards", views.ReportCardViewSet, basename="report-card")
router.register("comment-bank", views.CommentBankViewSet, basename="comment-bank")
router.register("uneb-results", views.UnebResultViewSet, basename="uneb-result")

urlpatterns = [
    path("public/verify/<str:token>/", views.VerifyReportCardView.as_view()),
    path("subject-comments/", views.SubjectCommentsView.as_view()),
    *router.urls,
]
