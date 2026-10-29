from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("library/books", views.BookViewSet, basename="book")
router.register("library/copies", views.BookCopyViewSet, basename="book-copy")
router.register("library/loans", views.LoanViewSet, basename="loan")

urlpatterns = router.urls
