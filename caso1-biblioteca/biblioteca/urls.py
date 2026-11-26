"""Rutas de la API (generadas por el router)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("libros", views.LibroViewSet, basename="libro")
router.register("autores", views.AutorViewSet, basename="autor")
router.register("categorias", views.CategoriaViewSet, basename="categoria")
router.register("prestamos", views.PrestamoViewSet, basename="prestamo")
router.register("usuarios", views.UsuarioViewSet, basename="usuario")

urlpatterns = [path("", include(router.urls))]
