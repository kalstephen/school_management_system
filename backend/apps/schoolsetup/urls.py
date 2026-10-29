from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("academic-years", views.AcademicYearViewSet, basename="academic-year")
router.register("terms", views.TermViewSet, basename="term")
router.register("sections", views.SectionViewSet, basename="section")
router.register("classes", views.SchoolClassViewSet, basename="class")
router.register("streams", views.StreamViewSet, basename="stream")
router.register("houses", views.HouseViewSet, basename="house")
router.register("departments", views.DepartmentViewSet, basename="department")
router.register("clubs", views.ClubViewSet, basename="club")
router.register("grading-scales", views.GradingScaleViewSet, basename="grading-scale")
router.register("grade-bands", views.GradeBandViewSet, basename="grade-band")
router.register("calendar", views.CalendarEventViewSet, basename="calendar")

urlpatterns = [
    path("school/", views.SchoolProfileView.as_view()),
    path("school/report-preview/", views.ReportPreviewView.as_view()),
    path("current-term/", views.CurrentTermView.as_view()),
    path("setup/seed-defaults/", views.SeedDefaultsView.as_view()),
    path("setup/generate-year/", views.GenerateYearView.as_view()),
    path("school-days/", views.SchoolDaysView.as_view()),
    path("class-teachers/", views.ClassTeachersView.as_view()),
    *router.urls,
]
