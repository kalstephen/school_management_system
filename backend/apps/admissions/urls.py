from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("applications", views.ApplicationViewSet, basename="application")
router.register("enquiries", views.EnquiryViewSet, basename="enquiry")
router.register("visitors", views.VisitorViewSet, basename="visitor")

urlpatterns = router.urls
