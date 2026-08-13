from django.urls import path

from .views import HealthView, MetaView

app_name = "platform_probe"

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("meta", MetaView.as_view(), name="meta"),
]
