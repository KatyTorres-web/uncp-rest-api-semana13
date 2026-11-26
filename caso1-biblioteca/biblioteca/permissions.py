"""Permisos de la API según los actores del sistema."""
from rest_framework import permissions

from .models import MAX_PRESTAMOS_ACTIVOS, Perfil, Prestamo


def es_bibliotecario(usuario):
    """Administrador (is_staff) o personal de atención (perfil bibliotecario)."""
    if not usuario or not usuario.is_authenticated:
        return False
    if usuario.is_staff:
        return True
    perfil = getattr(usuario, "perfil", None)
    return perfil is not None and perfil.tipo == Perfil.Tipo.BIBLIOTECARIO


class EsBibliotecarioOAdmin(permissions.BasePermission):
    message = "Solo el personal de biblioteca puede realizar esta acción."

    def has_permission(self, request, view):
        return es_bibliotecario(request.user)


class EsBibliotecarioOAdminOSoloLectura(EsBibliotecarioOAdmin):
    """Catálogo: cualquiera lee (incluye sistemas externos); solo el personal escribe."""

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or es_bibliotecario(request.user)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Lectura para todos; modificación solo del dueño del recurso (o admin)."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        dueno = getattr(obj, "usuario", obj)
        return request.user.is_staff or dueno == request.user


class EsPropietarioOPersonal(permissions.BasePermission):
    """Un préstamo solo lo ve su propietario o el personal de biblioteca."""

    message = "Solo puede consultar sus propios préstamos."

    def has_object_permission(self, request, view, obj):
        return es_bibliotecario(request.user) or obj.usuario == request.user


class PuedeCrearPrestamo(permissions.BasePermission):
    """Permiso personalizado: el usuario destino no debe superar 5 préstamos activos."""

    message = f"El usuario ya tiene {MAX_PRESTAMOS_ACTIVOS} préstamos activos (límite alcanzado)."

    def has_permission(self, request, view):
        if request.method != "POST":
            return True
        usuario_id = request.data.get("usuario")
        if not usuario_id:
            return True  # el serializador reportará el campo faltante
        activos = Prestamo.objects.filter(
            usuario_id=usuario_id, estado__in=[Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO]
        ).count()
        return activos < MAX_PRESTAMOS_ACTIVOS
