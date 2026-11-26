"""Serializadores de la API de la Biblioteca Central UNCP.

Pipeline: JSON -> to_internal_value() -> validate_<campo>() -> validate() -> save()
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from rest_framework import serializers

from .models import MAX_PRESTAMOS_ACTIVOS, Autor, Categoria, Libro, Perfil, Prestamo

User = get_user_model()


# ----------------------------------------------------------------------------- Catálogo
class AutorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Autor
        fields = ("id", "nombre", "nacionalidad", "biografia")


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ("id", "nombre", "slug")


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Crear libro",
            request_only=True,
            value={
                "isbn": "978-0262046305", "titulo": "Introduction to Algorithms", "autor_id": 1,
                "editorial": "MIT Press", "anio": 2022, "categoria": "ingenieria",
                "stock": 3, "estante": "A-12", "piso": 2,
            },
        )
    ]
)
class LibroSerializer(serializers.ModelSerializer):
    # HATEOAS: enlace al detalle del libro
    url = serializers.HyperlinkedIdentityField(view_name="libro-detail")
    # Nested serialization: autor completo (lectura) + autor_id (escritura)
    autor = AutorSerializer(read_only=True)
    autor_id = serializers.PrimaryKeyRelatedField(source="autor", queryset=Autor.objects.all(), write_only=True)
    categoria = serializers.SlugRelatedField(slug_field="slug", queryset=Categoria.objects.all())
    categoria_nombre = serializers.ReadOnlyField(source="categoria.nombre")
    # Campos calculados
    disponible = serializers.SerializerMethodField()
    ubicacion = serializers.SerializerMethodField()

    class Meta:
        model = Libro
        fields = (
            "id", "url", "isbn", "titulo", "autor", "autor_id", "editorial", "anio",
            "categoria", "categoria_nombre", "stock", "disponible", "estante", "piso", "ubicacion",
            "fecha_creacion",
        )
        read_only_fields = ("fecha_creacion",)

    def get_disponible(self, obj) -> bool:
        return obj.stock > 0

    def get_ubicacion(self, obj) -> str:
        return f"Piso {obj.piso} - Estante {obj.estante}"

    def validate_isbn(self, valor):
        limpio = valor.replace("-", "").replace(" ", "")
        if not limpio.isdigit() or len(limpio) not in (10, 13):
            raise serializers.ValidationError("El ISBN debe tener 10 o 13 dígitos.")
        return valor

    def validate_anio(self, valor):
        if valor > timezone.localdate().year:
            raise serializers.ValidationError("El año de publicación no puede ser futuro.")
        return valor


# ----------------------------------------------------------------------------- Préstamos
@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Registrar préstamo",
            request_only=True,
            value={"usuario": 3, "libro": 10, "fecha_devolucion": "2026-12-10"},
        )
    ]
)
class PrestamoSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="prestamo-detail")
    usuario_nombre = serializers.CharField(source="usuario.get_full_name", read_only=True)
    libro_titulo = serializers.ReadOnlyField(source="libro.titulo")
    libro_url = serializers.HyperlinkedRelatedField(source="libro", view_name="libro-detail", read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)
    multa = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    fecha_devolucion = serializers.DateField(required=False)

    class Meta:
        model = Prestamo
        fields = (
            "id", "url", "usuario", "usuario_nombre", "libro", "libro_titulo", "libro_url",
            "fecha_prestamo", "fecha_devolucion", "fecha_devuelto", "estado", "dias_restantes", "multa",
        )
        read_only_fields = ("fecha_prestamo", "fecha_devuelto", "estado")

    def validate_libro(self, libro):
        if libro.stock <= 0:
            raise serializers.ValidationError(f"El libro «{libro.titulo}» no tiene stock disponible.")
        return libro

    def validate_usuario(self, usuario):
        perfil = getattr(usuario, "perfil", None)
        if perfil is not None and not perfil.carnet_activo:
            raise serializers.ValidationError("El usuario no tiene el carnet activo.")
        activos = usuario.prestamos.filter(estado__in=[Prestamo.Estado.ACTIVO, Prestamo.Estado.VENCIDO]).count()
        if activos >= MAX_PRESTAMOS_ACTIVOS:
            raise serializers.ValidationError(
                f"El usuario ya tiene {activos} préstamos activos (máximo {MAX_PRESTAMOS_ACTIVOS})."
            )
        return usuario

    def validate(self, datos):
        fecha = datos.get("fecha_devolucion")
        if fecha and fecha <= timezone.localdate():
            raise serializers.ValidationError({"fecha_devolucion": "Debe ser una fecha posterior a hoy."})
        return datos

    @transaction.atomic
    def create(self, datos):
        # Descuenta stock de forma atómica (evita condiciones de carrera)
        actualizados = Libro.objects.filter(pk=datos["libro"].pk, stock__gt=0).update(stock=F("stock") - 1)
        if not actualizados:
            raise serializers.ValidationError({"libro": "El libro se quedó sin stock."})
        return super().create(datos)


class PrestamoResumenSerializer(serializers.ModelSerializer):
    """Versión corta para el historial dentro del perfil del usuario."""

    libro_titulo = serializers.ReadOnlyField(source="libro.titulo")
    multa = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = Prestamo
        fields = ("id", "libro", "libro_titulo", "fecha_prestamo", "fecha_devolucion", "estado", "multa")


# ----------------------------------------------------------------------------- Usuarios
class UsuarioPublicoSerializer(serializers.ModelSerializer):
    """Vista pública: solo nombre, tipo y carrera."""

    nombre = serializers.SerializerMethodField()
    tipo = serializers.ReadOnlyField(source="perfil.tipo")
    carrera = serializers.ReadOnlyField(source="perfil.carrera")

    class Meta:
        model = User
        fields = ("id", "nombre", "tipo", "carrera")

    def get_nombre(self, obj) -> str:
        return obj.get_full_name() or obj.username


class UsuarioPrivadoSerializer(UsuarioPublicoSerializer):
    """Vista privada (propio usuario o admin): agrega contacto e historial."""

    url = serializers.HyperlinkedIdentityField(view_name="usuario-detail")
    telefono = serializers.ReadOnlyField(source="perfil.telefono")
    carnet_activo = serializers.ReadOnlyField(source="perfil.carnet_activo")
    prestamos_activos = serializers.IntegerField(read_only=True)
    multa_total = serializers.SerializerMethodField()
    historial_prestamos = PrestamoResumenSerializer(source="prestamos", many=True, read_only=True)

    class Meta(UsuarioPublicoSerializer.Meta):
        fields = UsuarioPublicoSerializer.Meta.fields + (
            "url", "username", "email", "telefono", "carnet_activo",
            "prestamos_activos", "multa_total", "historial_prestamos",
        )

    def get_multa_total(self, obj) -> Decimal:
        return sum((p.multa for p in obj.prestamos.all()), Decimal("0.00"))
