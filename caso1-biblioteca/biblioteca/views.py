"""ViewSets de la API de la Biblioteca Central UNCP."""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from .filters import LibroFilter
from .models import Autor, Categoria, Libro, Prestamo
from .permissions import (
    EsBibliotecarioOAdmin, EsBibliotecarioOAdminOSoloLectura, EsPropietarioOPersonal,
    PuedeCrearPrestamo, es_bibliotecario,
)
from .serializers import (
    AutorSerializer, CategoriaSerializer, LibroSerializer, PrestamoSerializer,
    UsuarioPrivadoSerializer, UsuarioPublicoSerializer,
)

User = get_user_model()
auditoria = logging.getLogger("api.auditoria")


# ============================================================================ RF1 Libros
@extend_schema_view(
    list=extend_schema(
        summary="Listar catálogo (público, 20 por página)",
        parameters=[
            OpenApiParameter("año__gte", int, description="Año de publicación desde (alias de anio__gte)"),
            OpenApiParameter("ordering", str, description="titulo, -anio, stock (también acepta -año y título)"),
        ],
    ),
    retrieve=extend_schema(summary="Detalle de un libro con autor completo"),
    create=extend_schema(summary="Crear libro (admin o bibliotecario)"),
    update=extend_schema(summary="Reemplazar libro (admin o bibliotecario)"),
    partial_update=extend_schema(summary="Actualizar parcialmente (admin o bibliotecario)"),
    destroy=extend_schema(summary="Eliminar libro (solo admin)"),
)
@extend_schema(tags=["Libros"])
class LibroViewSet(viewsets.ModelViewSet):
    # select_related evita el problema N+1 (autor y categoría en la misma consulta)
    queryset = Libro.objects.select_related("autor", "categoria")
    serializer_class = LibroSerializer
    permission_classes = [EsBibliotecarioOAdminOSoloLectura]
    filterset_class = LibroFilter
    search_fields = ["titulo", "autor__nombre", "isbn", "editorial"]
    ordering_fields = ["titulo", "anio", "stock", "fecha_creacion"]
    ordering = ["titulo"]

    def get_permissions(self):
        if self.action == "destroy":
            return [permissions.IsAdminUser()]  # operación destructiva: solo admin
        return super().get_permissions()

    def perform_create(self, serializer):
        libro = serializer.save()
        auditoria.info("LIBRO_CREADO id=%s isbn=%s por=%s", libro.pk, libro.isbn, self.request.user)

    def perform_destroy(self, instance):
        auditoria.info("LIBRO_ELIMINADO id=%s isbn=%s por=%s", instance.pk, instance.isbn, self.request.user)
        instance.delete()


@extend_schema(tags=["Catálogo auxiliar"])
class AutorViewSet(viewsets.ModelViewSet):
    queryset = Autor.objects.all()
    serializer_class = AutorSerializer
    permission_classes = [EsBibliotecarioOAdminOSoloLectura]
    search_fields = ["nombre", "nacionalidad"]


@extend_schema(tags=["Catálogo auxiliar"])
class CategoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


# ============================================================================ RF2 Préstamos
class PrestamoPaginacion(LimitOffsetPagination):
    """LimitOffsetPagination para este endpoint específico: ?limit=10&offset=20"""

    default_limit = 20
    max_limit = 100


@extend_schema_view(
    list=extend_schema(summary="Listar préstamos (los propios; el personal ve todos)"),
    retrieve=extend_schema(summary="Detalle de préstamo (propietario o personal)"),
    create=extend_schema(summary="Registrar préstamo (bibliotecario o admin, máx. 5 activos)"),
    partial_update=extend_schema(summary="Actualizar préstamo (bibliotecario o admin)"),
    destroy=extend_schema(summary="Eliminar préstamo (solo admin)"),
)
@extend_schema(tags=["Préstamos"])
class PrestamoViewSet(viewsets.ModelViewSet):
    serializer_class = PrestamoSerializer
    pagination_class = PrestamoPaginacion
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["estado", "usuario", "libro"]
    search_fields = ["libro__titulo", "usuario__username"]
    ordering_fields = ["fecha_prestamo", "fecha_devolucion"]
    ordering = ["-fecha_prestamo"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # generación del esquema OpenAPI
            return Prestamo.objects.none()
        Prestamo.actualizar_vencidos()
        qs = Prestamo.objects.select_related("usuario", "libro")
        if es_bibliotecario(self.request.user):
            return qs
        return qs.filter(usuario=self.request.user)  # el estudiante solo ve lo suyo

    def get_permissions(self):
        if self.action == "create":
            clases = [permissions.IsAuthenticated, EsBibliotecarioOAdmin, PuedeCrearPrestamo]
        elif self.action in ("devolver", "vencidos", "partial_update"):
            clases = [permissions.IsAuthenticated, EsBibliotecarioOAdmin]
        elif self.action == "destroy":
            clases = [permissions.IsAdminUser]
        else:
            clases = [permissions.IsAuthenticated, EsPropietarioOPersonal]
        return [c() for c in clases]

    def perform_create(self, serializer):
        prestamo = serializer.save()
        auditoria.info("PRESTAMO_CREADO id=%s libro=%s usuario=%s por=%s",
                       prestamo.pk, prestamo.libro_id, prestamo.usuario_id, self.request.user)

    @extend_schema(summary="Marcar préstamo como devuelto (repone stock)", request=None,
                   responses=PrestamoSerializer)
    @action(detail=True, methods=["post"])
    def devolver(self, request, pk=None):
        prestamo = self.get_object()
        if prestamo.estado == Prestamo.Estado.DEVUELTO:
            return Response({"detail": "Este préstamo ya fue devuelto."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            prestamo.estado = Prestamo.Estado.DEVUELTO
            prestamo.fecha_devuelto = timezone.localdate()
            prestamo.save(update_fields=["estado", "fecha_devuelto"])
            Libro.objects.filter(pk=prestamo.libro_id).update(stock=F("stock") + 1)
        auditoria.info("PRESTAMO_DEVUELTO id=%s multa=%s por=%s", prestamo.pk, prestamo.multa, request.user)
        return Response(self.get_serializer(prestamo).data)

    @extend_schema(summary="Listar préstamos vencidos (con multa)")
    @action(detail=False, methods=["get"])
    def vencidos(self, request):
        vencidos = self.get_queryset().filter(estado=Prestamo.Estado.VENCIDO)
        pagina = self.paginate_queryset(vencidos)
        return self.get_paginated_response(self.get_serializer(pagina, many=True).data)


# ============================================================================ RF3 Usuarios
@extend_schema_view(
    list=extend_schema(summary="Listar usuarios (solo admin)"),
    retrieve=extend_schema(
        summary="Detalle de usuario",
        description="Propio usuario o admin: vista privada. Otro usuario autenticado: vista pública.",
    ),
)
@extend_schema(tags=["Usuarios"])
class UsuarioViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    search_fields = ["username", "first_name", "last_name", "perfil__carrera"]
    filterset_fields = ["perfil__tipo"]
    ordering_fields = ["username", "prestamos_activos"]
    ordering = ["username"]

    def get_queryset(self):
        activos = Count("prestamos", filter=Q(prestamos__estado__in=[Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO]))
        return (
            User.objects.select_related("perfil")
            .prefetch_related(Prefetch("prestamos", queryset=Prestamo.objects.select_related("libro")))
            .annotate(prestamos_activos=activos)
        )

    def get_permissions(self):
        if self.action == "list":
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        """Serialización diferenciada: privada para el dueño o admin, pública para los demás."""
        if self.action == "list" or self.action == "perfil":
            return UsuarioPrivadoSerializer
        if self.action == "retrieve":
            objeto_id = str(self.kwargs.get("pk"))
            if self.request.user.is_staff or str(self.request.user.pk) == objeto_id:
                return UsuarioPrivadoSerializer
        return UsuarioPublicoSerializer

    @extend_schema(summary="Perfil del usuario autenticado", responses=UsuarioPrivadoSerializer)
    @action(detail=False, methods=["get"])
    def perfil(self, request):
        usuario = self.get_queryset().get(pk=request.user.pk)
        return Response(self.get_serializer(usuario).data)
