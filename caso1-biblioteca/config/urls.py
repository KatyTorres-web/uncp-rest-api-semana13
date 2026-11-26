"""Rutas principales del proyecto."""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.authtoken.views import ObtainAuthToken

# Endpoint de token documentado en Swagger
ObtenerToken = extend_schema(tags=["Autenticación"], summary="Obtener token (usuario y contraseña)")(ObtainAuthToken)

urlpatterns = [
    path("", TemplateView.as_view(template_name="biblioteca/index.html"), name="inicio"),
    path("admin/", admin.site.urls),  # admin web: sesión + CSRF
    path("api/", include("biblioteca.urls")),
    path("api/auth/token/", ObtenerToken.as_view(), name="token"),
    path("api-auth/", include("rest_framework.urls")),
    # Documentación OpenAPI 3
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
