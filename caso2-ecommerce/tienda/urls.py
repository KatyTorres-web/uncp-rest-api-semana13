"""Rutas de la API (generadas por el router)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("productos", views.ProductoViewSet, basename="producto")
router.register("categorias", views.CategoriaViewSet, basename="categoria")
router.register("vendedores", views.VendedorViewSet, basename="vendedor")
router.register("carrito", views.CarritoViewSet, basename="carrito")
router.register("ordenes", views.OrdenViewSet, basename="orden")
router.register("reseñas", views.ResenaViewSet, basename="resena")  # ruta tal como pide el RF4

urlpatterns = [
    path("", include(router.urls)),
    path("webhooks/pago/", views.WebhookPagoView.as_view(), name="webhook-pago"),
]
