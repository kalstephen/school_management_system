from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("subjects", views.SubjectViewSet, basename="subject")
router.register("papers", views.PaperViewSet, basename="paper")
router.register("combinations", views.CombinationViewSet, basename="combination")
router.register("competencies", views.CompetencyViewSet, basename="competency")
router.register("allocations", views.SubjectAllocationViewSet, basename="allocation")
router.register("schemes", views.SchemeOfWorkViewSet, basename="scheme")

urlpatterns = router.urls
