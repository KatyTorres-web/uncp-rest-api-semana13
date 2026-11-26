"""Modelos de TecnoMarket Perú."""
import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

IGV = Decimal(settings.IGV)
DOS = Decimal("0.01")


def redondear(valor):
    return Decimal(valor).quantize(DOS, rounding=ROUND_HALF_UP)


class Perfil(models.Model):
    """Rol de cada usuario en la plataforma."""

    class Rol(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        VENDEDOR = "vendedor", "Vendedor"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.CLIENTE)
    nombre_tienda = models.CharField(max_length=80, blank=True)  # solo vendedores
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    puntos = models.PositiveIntegerField(default=0)  # programa de fidelidad

    def __str__(self):
        return f"{self.usuario.username} ({self.rol})"


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)  # ?categoria=laptops
    descripcion = models.CharField(max_length=200, blank=True)
    imagen = models.URLField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sku = models.CharField("SKU", max_length=30, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    marca = models.CharField(max_length=50)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="productos")
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("1.00"))])
    descuento = models.PositiveSmallIntegerField("descuento (%)", default=0, validators=[MaxValueValidator(90)])
    stock = models.PositiveIntegerField(default=0)
    especificaciones = models.JSONField(default=dict, blank=True)  # specs técnicas libres
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [models.Index(fields=["marca"]), models.Index(fields=["precio"]),
                   models.Index(fields=["fecha_creacion"])]

    def __str__(self):
        return self.nombre

    @property
    def precio_con_descuento(self):
        return redondear(self.precio * (100 - self.descuento) / 100)


class ImagenProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="imagenes")
    url = models.URLField()
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden"]


class Cupon(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    porcentaje = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(50)])
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo} (-{self.porcentaje}%)"


class Carrito(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carritos")
    activo = models.BooleanField(default=True)
    cupon = models.ForeignKey(Cupon, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Regla de negocio en la BD: un solo carrito activo por usuario
        constraints = [models.UniqueConstraint(fields=["usuario"], condition=Q(activo=True),
                                               name="un_carrito_activo_por_usuario")]

    def __str__(self):
        return f"Carrito de {self.usuario.username}"

    @property
    def subtotal(self):
        return redondear(sum((i.subtotal for i in self.items.all()), Decimal("0")))

    @property
    def descuento_cupon(self):
        return redondear(self.subtotal * self.cupon.porcentaje / 100) if self.cupon else Decimal("0.00")

    @property
    def impuestos(self):
        return redondear(self.subtotal * IGV)

    @property
    def total(self):
        return redondear(self.subtotal + self.impuestos)

    @property
    def total_con_descuento(self):
        """Total aplicando el cupón: (subtotal - descuento) + IGV."""
        return redondear((self.subtotal - self.descuento_cupon) * (1 + IGV))

    @property
    def cantidad_items(self):
        return sum(i.cantidad for i in self.items.all())


class ItemCarrito(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["carrito", "producto"], name="producto_unico_en_carrito")]

    @property
    def subtotal(self):
        return redondear(self.producto.precio_con_descuento * self.cantidad)


class Orden(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADA = "pagada", "Pagada"
        ENVIADA = "enviada", "Enviada"
        ENTREGADA = "entregada", "Entregada"
        CANCELADA = "cancelada", "Cancelada"

    class MetodoPago(models.TextChoices):
        CULQI = "culqi", "Culqi"
        MERCADOPAGO = "mercadopago", "MercadoPago"
        NIUBIZ = "niubiz", "Niubiz"
        CONTRAENTREGA = "contraentrega", "Pago contra entrega"

    # Transiciones de estado permitidas (máquina de estados)
    TRANSICIONES = {
        Estado.PENDIENTE: {Estado.PAGADA, Estado.CANCELADA},
        Estado.PAGADA: {Estado.ENVIADA, Estado.CANCELADA},
        Estado.ENVIADA: {Estado.ENTREGADA},
        Estado.ENTREGADA: set(),
        Estado.CANCELADA: set(),
    }

    numero = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ordenes")
    direccion_envio = models.CharField(max_length=200)
    metodo_pago = models.CharField(max_length=15, choices=MetodoPago.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    impuestos = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    numero_seguimiento = models.CharField(max_length=20, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [models.Index(fields=["estado"])]

    def __str__(self):
        return f"Orden {str(self.numero)[:8]} ({self.estado})"

    @property
    def tiempo_estimado_entrega(self):
        return {"desde": (self.fecha_creacion + timedelta(days=3)).date(),
                "hasta": (self.fecha_creacion + timedelta(days=5)).date()}

    def generar_seguimiento(self):
        """Número de seguimiento del courier al pasar a 'enviada' (ej.: OLV-3F9A2C1B)."""
        self.numero_seguimiento = f"OLV-{uuid.uuid4().hex[:8].upper()}"


class ItemOrden(models.Model):
    """Snapshot: guarda nombre y precio AL MOMENTO de la compra (no el precio actual)."""

    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, related_name="items_vendidos")
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    sku = models.CharField(max_length=30)
    nombre_producto = models.CharField(max_length=150)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return redondear(self.precio_unitario * self.cantidad)


class Resena(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resenas")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="resenas")
    calificacion = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    titulo = models.CharField(max_length=100)
    comentario = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "reseña"
        constraints = [models.UniqueConstraint(fields=["usuario", "producto"], name="una_resena_por_producto")]

    def __str__(self):
        return f"{self.producto} - {self.calificacion}/5"


def compro_producto(usuario, producto_id):
    """True si el usuario tiene una orden pagada/enviada/entregada con ese producto."""
    return ItemOrden.objects.filter(
        orden__usuario=usuario, producto_id=producto_id,
        orden__estado__in=[Orden.Estado.PAGADA, Orden.Estado.ENVIADA, Orden.Estado.ENTREGADA],
    ).exists()
