from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("staff", views.StaffProfileViewSet, basename="staff")
router.register("qualifications", views.QualificationViewSet, basename="qualification")
router.register("leave-requests", views.LeaveRequestViewSet, basename="leave-request")
router.register("duty-roster", views.DutyRosterViewSet, basename="duty-roster")
router.register("staff-attendance", views.StaffAttendanceViewSet, basename="staff-attendance")
router.register("planner", views.PlannerTaskViewSet, basename="planner")

urlpatterns = router.urls
