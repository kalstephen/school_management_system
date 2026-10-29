from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

API_APPS = [
    "accounts",
    "subscriptions",
    "schoolsetup",
    "curriculum",
    "learners",
    "admissions",
    "staff",
    "timetable",
    "attendance",
    "assessment",
    "promotion",
    "discipline",
    "communication",
    "finance",
    "library",
    "sickbay",
    "stores",
    "dashboard",
    "sync",
]


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    *[path("api/", include(f"apps.{app}.urls")) for app in API_APPS],
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
