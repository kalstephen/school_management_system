from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("periods", views.PeriodViewSet, basename="period")
router.register("rooms", views.RoomViewSet, basename="room")
router.register("timetable", views.SlotViewSet, basename="timetable")
router.register("substitutions", views.SubstitutionViewSet, basename="substitution")

urlpatterns = router.urls
