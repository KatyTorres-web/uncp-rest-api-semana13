"""Modelos de la Biblioteca Central UNCP."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

MULTA_POR_DIA = Decimal("2.00")
DIAS_PRESTAMO = 14
MAX_PRESTAMOS_ACTIVOS = 5


class Autor(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    nacionalidad = models.CharField(max_length=60)
    biografia = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "autores"

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)  # ?categoria=ingenieria

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Libro(models.Model):
    isbn = models.CharField("ISBN", max_length=17, unique=True)
    titulo = models.CharField("título", max_length=200)
    autor = models.ForeignKey(Autor, on_delete=models.PROTECT, related_name="libros")
    editorial = models.CharField(max_length=100)
    anio = models.PositiveSmallIntegerField(
        "año", validators=[MinValueValidator(1450), MaxValueValidator(2100)]
    )
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="libros")
    stock = models.PositiveIntegerField(default=1)
    estante = models.CharField(max_length=10)
    piso = models.PositiveSmallIntegerField(default=1)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["titulo"]
        # Índices en los campos más filtrados/ordenados (rendimiento < 200 ms)
        indexes = [models.Index(fields=["anio"]), models.Index(fields=["titulo"]), models.Index(fields=["stock"])]

    def __str__(self):
        return f"{self.titulo} ({self.anio})"


class Perfil(models.Model):
    """Datos de biblioteca de cada usuario (extiende a auth.User)."""

    class Tipo(models.TextChoices):
        ESTUDIANTE = "estudiante", "Estudiante"
        DOCENTE = "docente", "Docente"
        INVESTIGADOR = "investigador", "Investigador"
        BIBLIOTECARIO = "bibliotecario", "Bibliotecario"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.ESTUDIANTE)
    carrera = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=15, blank=True)
    carnet_activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.usuario.username} ({self.get_tipo_display()})"


class Prestamo(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        DEVUELTO = "devuelto", "Devuelto"
        VENCIDO = "vencido", "Vencido"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prestamos")
    libro = models.ForeignKey(Libro, on_delete=models.PROTECT, related_name="prestamos")
    fecha_prestamo = models.DateField(default=timezone.localdate)
    fecha_devolucion = models.DateField("fecha límite de devolución")
    fecha_devuelto = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)

    class Meta:
        ordering = ["-fecha_prestamo", "-id"]
        indexes = [models.Index(fields=["estado"]), models.Index(fields=["fecha_devolucion"])]

    def __str__(self):
        return f"{self.libro.titulo} -> {self.usuario.username} ({self.estado})"

    def save(self, *args, **kwargs):
        if not self.fecha_devolucion:
            self.fecha_devolucion = (self.fecha_prestamo or timezone.localdate()) + timedelta(days=DIAS_PRESTAMO)
        super().save(*args, **kwargs)

    @classmethod
    def actualizar_vencidos(cls):
        """Pasa a 'vencido' los préstamos activos cuya fecha límite ya pasó."""
        return cls.objects.filter(estado=cls.Estado.ACTIVO, fecha_devolucion__lt=timezone.localdate()).update(
            estado=cls.Estado.VENCIDO
        )

    @property
    def dias_restantes(self):
        if self.estado == self.Estado.DEVUELTO:
            return 0
        return (self.fecha_devolucion - timezone.localdate()).days

    @property
    def multa(self):
        """S/ 2.00 por cada día de retraso."""
        fin = self.fecha_devuelto or timezone.localdate()
        dias_retraso = (fin - self.fecha_devolucion).days
        return MULTA_POR_DIA * dias_retraso if dias_retraso > 0 else Decimal("0.00")
