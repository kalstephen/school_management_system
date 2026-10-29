from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("notices", views.NoticeViewSet, basename="notice")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("email-log", views.EmailLogViewSet, basename="email-log")

urlpatterns = router.urls
