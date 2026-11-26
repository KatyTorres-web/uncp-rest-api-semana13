"""ViewSets de la API de TecnoMarket Perú."""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count, F, Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .filters import ProductoFilter
from .models import Carrito, Categoria, ItemCarrito, Orden, Perfil, Producto, Resena
from .pagination import PaginacionOrdenes
from .permissions import EsCompradorVerificado, IsOwnerOrReadOnly, PuedeActualizarOrden, PuedeVender, es_vendedor
from .serializers import (
    AgregarItemSerializer, CarritoSerializer, CategoriaSerializer, CheckoutSerializer, CuponSerializer,
    EliminarItemSerializer, OrdenSerializer, ProductoSerializer, ResenaSerializer, VendedorSerializer,
)
from .throttling import CheckoutRateThrottle

User = get_user_model()
auditoria = logging.getLogger("api.auditoria")


# ============================================================================ RF1 Productos
@extend_schema_view(
    list=extend_schema(summary="Catálogo público (24 por página)", parameters=[
        OpenApiParameter("ordering", str, description="precio, -precio, rating_promedio, -fecha_creacion, nombre"),
    ]),
    retrieve=extend_schema(summary="Detalle con especificaciones completas"),
    create=extend_schema(summary="Publicar producto (vendedor o admin)"),
    update=extend_schema(summary="Reemplazar producto (dueño o admin)"),
    partial_update=extend_schema(summary="Actualizar producto (dueño o admin)"),
    destroy=extend_schema(summary="Eliminar producto (solo admin)"),
)
@extend_schema(tags=["Productos"])
class ProductoViewSet(viewsets.ModelViewSet):
    serializer_class = ProductoSerializer
    filterset_class = ProductoFilter
    search_fields = ["nombre", "descripcion", "marca", "categoria__nombre"]  # ?search=gaming laptop
    ordering_fields = ["precio", "rating_promedio", "fecha_creacion", "nombre", "stock"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        # Una sola consulta con rating y total de reseñas anotados + prefetch de imágenes (sin N+1)
        return (
            Producto.objects.filter(activo=True)
            .select_related("categoria", "vendedor__perfil")
            .prefetch_related("imagenes")
            .annotate(rating_promedio=Avg("resenas__calificacion"), total_resenas=Count("resenas", distinct=True))
        )

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), PuedeVender()]
        if self.action in ("update", "partial_update"):
            return [permissions.IsAuthenticated(), PuedeVender(), IsOwnerOrReadOnly()]
        if self.action == "destroy":
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        producto = serializer.save(vendedor=self.request.user)  # el vendedor es quien publica
        auditoria.info("PRODUCTO_CREADO sku=%s por=%s", producto.sku, self.request.user)

    def perform_destroy(self, instance):
        auditoria.info("PRODUCTO_ELIMINADO sku=%s por=%s", instance.sku, self.request.user)
        instance.delete()

    @extend_schema(summary="Reseñas de un producto", tags=["Reseñas"], responses=ResenaSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="reseñas")
    def resenas(self, request, pk=None):
        producto = self.get_object()
        resenas = producto.resenas.select_related("usuario")
        pagina = self.paginate_queryset(resenas)
        return self.get_paginated_response(ResenaSerializer(pagina, many=True, context={"request": request}).data)


@extend_schema(tags=["Productos"])
class CategoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


@extend_schema(tags=["Productos"], summary="Tiendas del marketplace (datos públicos)")
class VendedorViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VendedorSerializer
    permission_classes = [permissions.AllowAny]
    queryset = User.objects.filter(perfil__rol=Perfil.Rol.VENDEDOR).select_related("perfil").annotate(
        productos_publicados=Count("productos")
    ).order_by("id")


# ============================================================================ RF2 Carrito
@extend_schema(tags=["Carrito"])
class CarritoViewSet(viewsets.GenericViewSet):
    """El carrito es un recurso único por usuario: todas las acciones son detail=False."""

    serializer_class = CarritoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Carrito.objects.none()
        return Carrito.objects.filter(usuario=self.request.user, activo=True)

    def carrito_actual(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.request.user, activo=True)
        return Carrito.objects.prefetch_related(
            Prefetch("items", queryset=ItemCarrito.objects.select_related("producto"))
        ).select_related("cupon").get(pk=carrito.pk)

    def responder(self, carrito, codigo=status.HTTP_200_OK):
        return Response(CarritoSerializer(self.carrito_actual() if carrito is None else carrito,
                                          context={"request": self.request}).data, status=codigo)

    @extend_schema(summary="Ver carrito actual")
    def list(self, request):
        return self.responder(self.carrito_actual())

    @extend_schema(summary="Agregar producto", request=AgregarItemSerializer, responses=CarritoSerializer)
    @action(detail=False, methods=["post"])
    def agregar(self, request):
        carrito = self.carrito_actual()
        entrada = AgregarItemSerializer(data=request.data, context={"carrito": carrito, "sumar": True})
        entrada.is_valid(raise_exception=True)
        ItemCarrito.objects.update_or_create(carrito=carrito, producto=entrada.validated_data["producto"],
                                             defaults={"cantidad": entrada.validated_data["cantidad_final"]})
        return self.responder(None)

    @extend_schema(summary="Actualizar cantidad", request=AgregarItemSerializer, responses=CarritoSerializer)
    @action(detail=False, methods=["post"])
    def actualizar(self, request):
        carrito = self.carrito_actual()
        entrada = AgregarItemSerializer(data=request.data, context={"carrito": carrito, "sumar": False})
        entrada.is_valid(raise_exception=True)
        item = carrito.items.filter(producto=entrada.validated_data["producto"]).first()
        if not item:
            return Response({"detail": "El producto no está en el carrito."}, status=status.HTTP_404_NOT_FOUND)
        item.cantidad = entrada.validated_data["cantidad_final"]
        item.save(update_fields=["cantidad"])
        return self.responder(None)

    @extend_schema(summary="Eliminar producto del carrito", request=EliminarItemSerializer,
                   responses=CarritoSerializer)
    @action(detail=False, methods=["post"])
    def eliminar(self, request):
        carrito = self.carrito_actual()
        entrada = EliminarItemSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        borrados, _ = carrito.items.filter(producto=entrada.validated_data["producto"]).delete()
        if not borrados:
            return Response({"detail": "El producto no está en el carrito."}, status=status.HTTP_404_NOT_FOUND)
        return self.responder(None)

    @extend_schema(summary="Vaciar carrito", request=None, responses=CarritoSerializer)
    @action(detail=False, methods=["post"])
    def vaciar(self, request):
        carrito = self.carrito_actual()
        carrito.items.all().delete()
        carrito.cupon = None
        carrito.save(update_fields=["cupon"])
        return self.responder(None)

    @extend_schema(summary="Aplicar cupón de descuento", request=CuponSerializer, responses=CarritoSerializer)
    @action(detail=False, methods=["post"], url_path="aplicar-cupon")
    def aplicar_cupon(self, request):
        carrito = self.carrito_actual()
        entrada = CuponSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        carrito.cupon = entrada.validated_data["codigo"]
        carrito.save(update_fields=["cupon"])
        return self.responder(None)

    @extend_schema(summary="Checkout: convertir carrito en orden (máx. 10 por hora)", request=CheckoutSerializer,
                   responses={201: OrdenSerializer})
    @action(detail=False, methods=["post"],
            throttle_classes=[AnonRateThrottle, UserRateThrottle, CheckoutRateThrottle])
    def checkout(self, request):
        entrada = CheckoutSerializer(data=request.data, context={"carrito": self.carrito_actual()})
        entrada.is_valid(raise_exception=True)
        orden = entrada.save()
        auditoria.info("CHECKOUT orden=%s total=%s usuario=%s", orden.numero, orden.total, request.user)
        return Response(OrdenSerializer(orden, context={"request": request}).data, status=status.HTTP_201_CREATED)


# ============================================================================ RF3 Órdenes
@extend_schema_view(
    list=extend_schema(summary="Listar órdenes (cliente: propias; vendedor: con sus productos; admin: todas)"),
    retrieve=extend_schema(summary="Detalle de orden (propietario, vendedor o admin)"),
    create=extend_schema(summary="Crear orden desde el carrito", request=CheckoutSerializer,
                         responses={201: OrdenSerializer}),
    partial_update=extend_schema(
        summary="Actualizar estado (admin o vendedor)",
        request=inline_serializer("EstadoOrden", {"estado": serializers.ChoiceField(choices=Orden.Estado.choices)}),
    ),
)
@extend_schema(tags=["Órdenes"])
class OrdenViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = OrdenSerializer
    pagination_class = PaginacionOrdenes  # LimitOffset de 50
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["estado", "metodo_pago"]
    ordering_fields = ["fecha_creacion", "total"]
    ordering = ["-fecha_creacion"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Orden.objects.none()
        usuario = self.request.user
        qs = Orden.objects.select_related("usuario").prefetch_related("items")
        if usuario.is_staff:
            return qs
        if es_vendedor(usuario):
            return qs.filter(Q(usuario=usuario) | Q(items__vendedor=usuario)).distinct()
        return qs.filter(usuario=usuario)

    def get_permissions(self):
        if self.action == "partial_update":
            return [permissions.IsAuthenticated(), PuedeActualizarOrden()]
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action == "create":  # crear orden = checkout: mismo límite
            return [AnonRateThrottle(), UserRateThrottle(), CheckoutRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        carrito = Carrito.objects.filter(usuario=request.user, activo=True).first()
        if carrito is None:
            return Response({"detail": "No tiene un carrito activo."}, status=status.HTTP_400_BAD_REQUEST)
        entrada = CheckoutSerializer(data=request.data, context={"carrito": carrito})
        entrada.is_valid(raise_exception=True)
        orden = entrada.save()
        auditoria.info("ORDEN_CREADA orden=%s total=%s usuario=%s", orden.numero, orden.total, request.user)
        return Response(self.get_serializer(orden).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        anterior = serializer.instance.estado
        orden = serializer.save()
        auditoria.info("ORDEN_ESTADO orden=%s %s->%s por=%s", orden.numero, anterior, orden.estado, self.request.user)

    @extend_schema(summary="Cancelar orden (solo si está pendiente; repone stock)", request=None,
                   responses=OrdenSerializer)
    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        orden = self.get_object()
        if orden.usuario != request.user and not request.user.is_staff:
            return Response({"detail": "Solo el comprador o el admin pueden cancelar."},
                            status=status.HTTP_403_FORBIDDEN)
        if orden.estado != Orden.Estado.PENDIENTE:
            return Response({"detail": f"No se puede cancelar una orden '{orden.estado}'."},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for item in orden.items.all():
                if item.producto_id:
                    Producto.objects.filter(pk=item.producto_id).update(stock=F("stock") + item.cantidad)
            orden.estado = Orden.Estado.CANCELADA
            orden.save(update_fields=["estado", "fecha_actualizacion"])
        auditoria.info("ORDEN_CANCELADA orden=%s por=%s", orden.numero, request.user)
        return Response(self.get_serializer(orden).data)

    @extend_schema(summary="Mis órdenes (usuario autenticado)")
    @action(detail=False, methods=["get"], url_path="mis-ordenes")
    def mis_ordenes(self, request):
        ordenes = self.filter_queryset(self.get_queryset().filter(usuario=request.user))
        pagina = self.paginate_queryset(ordenes)
        return self.get_paginated_response(self.get_serializer(pagina, many=True).data)


# ============================================================================ RF4 Reseñas
@extend_schema_view(
    list=extend_schema(summary="Listar reseñas (público)"),
    retrieve=extend_schema(summary="Ver reseña"),
    create=extend_schema(summary="Publicar reseña (solo compradores verificados)"),
    destroy=extend_schema(summary="Eliminar reseña (autor o admin)"),
)
@extend_schema(tags=["Reseñas"])
class ResenaViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Resena.objects.select_related("usuario", "producto")
    serializer_class = ResenaSerializer
    filterset_fields = ["producto", "calificacion"]
    ordering_fields = ["fecha_creacion", "calificacion"]
    ordering = ["-fecha_creacion"]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), EsCompradorVerificado()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


# ============================================================================ Webhooks
@extend_schema(
    tags=["Integraciones"],
    summary="Webhook de pasarela de pago (Culqi / MercadoPago / Niubiz)",
    description="Cabecera obligatoria `X-Webhook-Token`. Marca la orden como pagada.",
    request=inline_serializer("WebhookPago", {"numero": serializers.UUIDField(),
                                              "estado": serializers.CharField(default="pagada")}),
    responses={200: OrdenSerializer},
)
class WebhookPagoView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if request.headers.get("X-Webhook-Token") != settings.WEBHOOK_TOKEN:
            return Response({"detail": "Webhook no autorizado."}, status=status.HTTP_401_UNAUTHORIZED)
        orden = Orden.objects.filter(numero=request.data.get("numero")).first()
        if orden is None:
            return Response({"detail": "Orden no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if orden.estado != Orden.Estado.PENDIENTE:
            return Response({"detail": f"La orden ya está '{orden.estado}'."}, status=status.HTTP_409_CONFLICT)
        orden.estado = Orden.Estado.PAGADA
        orden.save(update_fields=["estado", "fecha_actualizacion"])
        auditoria.info("WEBHOOK_PAGO orden=%s", orden.numero)
        return Response(OrdenSerializer(orden, context={"request": request}).data)
