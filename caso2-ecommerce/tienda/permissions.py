"""Permisos de TecnoMarket según los actores del sistema."""
from rest_framework import permissions

from .models import Perfil, compro_producto


def es_vendedor(usuario):
    perfil = getattr(usuario, "perfil", None)
    return usuario.is_authenticated and perfil is not None and perfil.rol == Perfil.Rol.VENDEDOR


class PuedeVender(permissions.BasePermission):
    """Solo vendedores del marketplace o administradores publican productos."""

    message = "Solo los vendedores registrados pueden publicar productos."

    def has_permission(self, request, view):
        return request.user.is_staff or es_vendedor(request.user)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Lectura pública; modificar solo el dueño (campo usuario o vendedor) o el admin."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        dueno = getattr(obj, "usuario", None) or getattr(obj, "vendedor", None)
        return request.user.is_staff or dueno == request.user


class EsCompradorVerificado(permissions.BasePermission):
    """Solo puede reseñar quien compró el producto (orden pagada, enviada o entregada)."""

    message = "Solo puede reseñar productos que ha comprado."

    def has_permission(self, request, view):
        if request.method != "POST":
            return True
        if request.user.is_staff:
            return True
        producto_id = str(request.data.get("producto", ""))
        return producto_id.isdigit() and compro_producto(request.user, producto_id)


class PuedeActualizarOrden(permissions.BasePermission):
    """El estado de una orden lo cambia el admin o un vendedor con productos en ella."""

    message = "Solo el administrador o el vendedor de los productos puede cambiar el estado."

    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.items.filter(vendedor=request.user).exists()
