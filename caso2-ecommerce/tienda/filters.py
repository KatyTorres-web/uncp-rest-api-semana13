"""Filtros del catálogo de productos."""
import django_filters

from .models import Producto


class ProductoFilter(django_filters.FilterSet):
    """?categoria=laptops&marca=dell&precio_min=500&precio_max=2000&disponible=true"""

    categoria = django_filters.CharFilter(field_name="categoria__slug", lookup_expr="iexact")
    marca = django_filters.CharFilter(lookup_expr="iexact")
    precio_min = django_filters.NumberFilter(field_name="precio", lookup_expr="gte")
    precio_max = django_filters.NumberFilter(field_name="precio", lookup_expr="lte")
    disponible = django_filters.BooleanFilter(method="filtrar_disponible")
    con_descuento = django_filters.BooleanFilter(method="filtrar_descuento")
    vendedor = django_filters.NumberFilter(field_name="vendedor_id")

    class Meta:
        model = Producto
        fields = ["categoria", "marca", "vendedor"]

    def filtrar_disponible(self, queryset, nombre, valor):
        return queryset.filter(stock__gt=0) if valor else queryset.filter(stock=0)

    def filtrar_descuento(self, queryset, nombre, valor):
        return queryset.filter(descuento__gt=0) if valor else queryset.filter(descuento=0)
