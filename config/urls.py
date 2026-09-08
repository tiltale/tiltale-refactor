"""Root URLs stay tiny; the studio app owns TilTale's routes."""

from django.urls import include, path

urlpatterns = [
    path("", include("studio.urls")),
]
