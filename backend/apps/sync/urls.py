from django.urls import path

from . import views

urlpatterns = [
    path("sync/", views.SyncView.as_view()),
    path("sync/conflicts/", views.ConflictsView.as_view()),
]
