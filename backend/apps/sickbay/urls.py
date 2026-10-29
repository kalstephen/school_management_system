from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sickbay/visits", views.SickbayVisitViewSet, basename="sickbay-visit")
router.register("sickbay/immunisations", views.ImmunisationViewSet, basename="immunisation")

urlpatterns = router.urls
