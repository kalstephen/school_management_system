from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("learners", views.LearnerViewSet, basename="learner")
router.register("guardians", views.GuardianViewSet, basename="guardian")
router.register("learner-guardians", views.LearnerGuardianViewSet, basename="learner-guardian")
router.register("enrolments", views.EnrolmentViewSet, basename="enrolment")
router.register("subject-enrolments", views.SubjectEnrolmentViewSet, basename="subject-enrolment")
router.register("learner-documents", views.LearnerDocumentViewSet, basename="learner-document")
router.register("learner-exits", views.LearnerExitViewSet, basename="learner-exit")
router.register("stream-changes", views.StreamChangeViewSet, basename="stream-change")

urlpatterns = router.urls
