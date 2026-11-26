"""Serializadores de TecnoMarket Perú.

Pipeline: JSON -> to_internal_value() -> validate_<campo>() -> validate() -> save()
"""
from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import OpenApiExample, extend_schema_field, extend_schema_serializer
from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import (
    IGV, Carrito, Categoria, Cupon, ImagenProducto, ItemCarrito, ItemOrden, Orden, Producto, Resena,
    compro_producto, redondear,
)


# ----------------------------------------------------------------------------- RF1 Catálogo
class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ("id", "nombre", "slug", "descripcion", "imagen")


class ImagenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenProducto
        fields = ("url", "orden")


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Publicar laptop",
            request_only=True,
            value={
                "sku": "LAP-DELL-G15-01", "nombre": "Dell G15 Gaming", "marca": "Dell", "categoria_id": 1,
                "precio": "4299.00", "descuento": 10, "stock": 15,
                "descripcion": "Laptop gamer con RTX 4060",
                "especificaciones": {"procesador": "Intel Core i7-13650HX", "ram": "16 GB DDR5",
                                     "almacenamiento": "1 TB SSD", "gpu": "RTX 4060 8 GB"},
                "imagenes_urls": ["https://cdn.tecnomarket.pe/dell-g15-1.jpg"],
            },
        )
    ]
)
class ProductoSerializer(serializers.ModelSerializer):
    # HATEOAS
    url = serializers.HyperlinkedIdentityField(view_name="producto-detail")
    vendedor_url = serializers.HyperlinkedRelatedField(source="vendedor", view_name="vendedor-detail", read_only=True)
    resenas_url = serializers.HyperlinkedIdentityField(view_name="producto-resenas")
    vendedor = serializers.CharField(source="vendedor.perfil.nombre_tienda", read_only=True)
    # Nested: categoría completa en lectura, categoria_id en escritura
    categoria = CategoriaSerializer(read_only=True)
    categoria_id = serializers.PrimaryKeyRelatedField(source="categoria", queryset=Categoria.objects.all(),
                                                      write_only=True)
    imagenes = ImagenSerializer(many=True, read_only=True)
    imagenes_urls = serializers.ListField(child=serializers.URLField(), write_only=True, required=False)
    # Campos calculados (rating viene anotado desde la vista: sin N+1)
    precio_con_descuento = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    rating_promedio = serializers.SerializerMethodField()
    total_resenas = serializers.IntegerField(read_only=True, default=0)
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = (
            "id", "url", "sku", "nombre", "descripcion", "marca", "categoria", "categoria_id",
            "precio", "descuento", "precio_con_descuento", "stock", "disponible",
            "rating_promedio", "total_resenas", "especificaciones", "imagenes", "imagenes_urls",
            "vendedor", "vendedor_url", "resenas_url", "fecha_creacion",
        )
        read_only_fields = ("fecha_creacion",)

    def get_rating_promedio(self, obj) -> float | None:
        valor = getattr(obj, "rating_promedio", None)
        return round(valor, 1) if valor is not None else None

    def get_disponible(self, obj) -> bool:
        return obj.stock > 0

    def validate_especificaciones(self, valor):
        if not isinstance(valor, dict):
            raise serializers.ValidationError("Debe ser un objeto JSON: {\"ram\": \"16 GB\", ...}")
        return valor

    def validate_sku(self, valor):
        return valor.strip().upper()

    def create(self, datos):
        urls = datos.pop("imagenes_urls", [])
        producto = super().create(datos)
        ImagenProducto.objects.bulk_create(
            [ImagenProducto(producto=producto, url=u, orden=i) for i, u in enumerate(urls)]
        )
        return producto

    def update(self, instancia, datos):
        urls = datos.pop("imagenes_urls", None)
        producto = super().update(instancia, datos)
        if urls is not None:
            producto.imagenes.all().delete()
            ImagenProducto.objects.bulk_create(
                [ImagenProducto(producto=producto, url=u, orden=i) for i, u in enumerate(urls)]
            )
        return producto


# ----------------------------------------------------------------------------- RF2 Carrito
class ItemCarritoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source="producto.nombre")
    producto_url = serializers.HyperlinkedRelatedField(source="producto", view_name="producto-detail", read_only=True)
    precio_unitario = serializers.DecimalField(source="producto.precio_con_descuento", max_digits=10,
                                               decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ItemCarrito
        fields = ("producto", "producto_nombre", "producto_url", "precio_unitario", "cantidad", "subtotal")


class CarritoSerializer(serializers.ModelSerializer):
    items = ItemCarritoSerializer(many=True, read_only=True)
    cupon = serializers.SlugRelatedField(slug_field="codigo", read_only=True)
    cantidad_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    impuestos = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    descuento_cupon = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_con_descuento = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    _links = serializers.SerializerMethodField()

    class Meta:
        model = Carrito
        fields = ("id", "usuario", "items", "cantidad_items", "subtotal", "impuestos", "total",
                  "cupon", "descuento_cupon", "total_con_descuento", "_links")

    def get__links(self, obj) -> dict:
        r = self.context.get("request")
        return {accion: reverse(f"carrito-{accion}", request=r)
                for accion in ("agregar", "actualizar", "eliminar", "vaciar", "checkout")}


class AgregarItemSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(activo=True))
    cantidad = serializers.IntegerField(min_value=1, max_value=50, default=1)

    def validate(self, datos):
        carrito = self.context["carrito"]
        producto, cantidad = datos["producto"], datos["cantidad"]
        if self.context.get("sumar", True):  # agregar suma a lo que ya hay en el carrito
            item = carrito.items.filter(producto=producto).first()
            cantidad += item.cantidad if item else 0
        if cantidad > producto.stock:
            raise serializers.ValidationError(
                {"cantidad": f"Solo hay {producto.stock} unidades de «{producto.nombre}» en stock."}
            )
        datos["cantidad_final"] = cantidad
        return datos


class EliminarItemSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())


class CuponSerializer(serializers.Serializer):
    codigo = serializers.SlugRelatedField(slug_field="codigo", queryset=Cupon.objects.filter(activo=True),
                                          error_messages={"does_not_exist": "Cupón inválido o vencido."})


@extend_schema_serializer(
    examples=[OpenApiExample("Checkout", request_only=True,
                             value={"direccion_envio": "Jr. Puno 456, Huancayo", "metodo_pago": "culqi"})]
)
class CheckoutSerializer(serializers.Serializer):
    direccion_envio = serializers.CharField(max_length=200)
    metodo_pago = serializers.ChoiceField(choices=Orden.MetodoPago.choices)

    def validate(self, datos):
        carrito = self.context["carrito"]
        if not carrito.items.exists():
            raise serializers.ValidationError("El carrito está vacío.")
        sin_stock = [i.producto.nombre for i in carrito.items.select_related("producto")
                     if i.cantidad > i.producto.stock]
        if sin_stock:
            raise serializers.ValidationError({"stock": f"Stock insuficiente: {', '.join(sin_stock)}"})
        return datos

    @transaction.atomic
    def save(self, **kwargs):
        """Convierte el carrito en orden: snapshot de precios, descuento de stock y puntos."""
        carrito = self.context["carrito"]
        items = list(carrito.items.select_related("producto"))
        subtotal, descuento = carrito.subtotal, carrito.descuento_cupon
        base = subtotal - descuento
        orden = Orden.objects.create(
            usuario=carrito.usuario, subtotal=subtotal, descuento=descuento,
            impuestos=redondear(base * IGV),
            total=carrito.total_con_descuento, **self.validated_data,
        )
        for item in items:
            # Descuento atómico: si otro cliente compró antes, la condición stock__gte falla
            if not Producto.objects.filter(pk=item.producto_id, stock__gte=item.cantidad).update(
                    stock=F("stock") - item.cantidad):
                raise serializers.ValidationError({"stock": f"«{item.producto.nombre}» se agotó."})
            ItemOrden.objects.create(
                orden=orden, producto=item.producto, vendedor_id=item.producto.vendedor_id,
                sku=item.producto.sku, nombre_producto=item.producto.nombre,
                precio_unitario=item.producto.precio_con_descuento, cantidad=item.cantidad,
            )
        carrito.activo = False
        carrito.save(update_fields=["activo"])
        perfil = getattr(carrito.usuario, "perfil", None)
        if perfil:  # programa de fidelidad: 1 punto por cada S/ 10
            perfil.puntos += int(orden.total // 10)
            perfil.save(update_fields=["puntos"])
        return orden


# ----------------------------------------------------------------------------- RF3 Órdenes
class ItemOrdenSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ItemOrden
        fields = ("sku", "nombre_producto", "producto", "precio_unitario", "cantidad", "subtotal")


class TiempoEntregaSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()


class OrdenSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="orden-detail")
    cliente = serializers.ReadOnlyField(source="usuario.username")
    items = ItemOrdenSerializer(many=True, read_only=True)  # snapshot del momento de compra
    tiempo_estimado_entrega = serializers.SerializerMethodField()

    class Meta:
        model = Orden
        fields = ("id", "url", "numero", "cliente", "items", "direccion_envio", "metodo_pago", "estado",
                  "subtotal", "descuento", "impuestos", "total", "numero_seguimiento",
                  "tiempo_estimado_entrega", "fecha_creacion", "fecha_actualizacion")
        read_only_fields = ("numero", "direccion_envio", "metodo_pago", "subtotal", "descuento", "impuestos",
                            "total", "numero_seguimiento", "fecha_creacion", "fecha_actualizacion")

    @extend_schema_field(TiempoEntregaSerializer)
    def get_tiempo_estimado_entrega(self, obj):
        return TiempoEntregaSerializer(obj.tiempo_estimado_entrega).data

    def validate_estado(self, nuevo):
        actual = self.instance.estado if self.instance else Orden.Estado.PENDIENTE
        if self.instance and nuevo != actual and nuevo not in Orden.TRANSICIONES[actual]:
            permitidos = ", ".join(sorted(Orden.TRANSICIONES[actual])) or "ninguno"
            raise serializers.ValidationError(f"No se puede pasar de '{actual}' a '{nuevo}'. Permitidos: {permitidos}.")
        return nuevo

    def update(self, instancia, datos):
        if datos.get("estado") == Orden.Estado.ENVIADA and not instancia.numero_seguimiento:
            instancia.generar_seguimiento()  # numero_seguimiento solo se genera al enviar
        return super().update(instancia, datos)


# ----------------------------------------------------------------------------- RF4 Reseñas
class ResenaSerializer(serializers.ModelSerializer):
    usuario = serializers.ReadOnlyField(source="usuario.username")
    producto_nombre = serializers.ReadOnlyField(source="producto.nombre")
    es_compra_verificada = serializers.SerializerMethodField()

    class Meta:
        model = Resena
        fields = ("id", "usuario", "producto", "producto_nombre", "calificacion", "titulo", "comentario",
                  "es_compra_verificada", "fecha_creacion")
        read_only_fields = ("fecha_creacion",)

    def get_es_compra_verificada(self, obj) -> bool:
        return compro_producto(obj.usuario, obj.producto_id)

    def validate_calificacion(self, valor):
        if not 1 <= valor <= 5:
            raise serializers.ValidationError("La calificación debe estar entre 1 y 5.")
        return valor

    def validate(self, datos):
        usuario = self.context["request"].user
        producto = datos["producto"]
        if not compro_producto(usuario, producto.pk) and not usuario.is_staff:
            raise serializers.ValidationError({"producto": "Solo puede reseñar productos que ha comprado."})
        if Resena.objects.filter(usuario=usuario, producto=producto).exists():
            raise serializers.ValidationError({"producto": "Ya publicó una reseña de este producto."})
        return datos


class VendedorSerializer(serializers.Serializer):
    """Datos públicos de una tienda del marketplace."""

    id = serializers.IntegerField()
    url = serializers.HyperlinkedIdentityField(view_name="vendedor-detail")
    nombre_tienda = serializers.CharField(source="perfil.nombre_tienda")
    productos_publicados = serializers.IntegerField()
