"""Filtros del catálogo."""
import django_filters
from rest_framework.filters import OrderingFilter

from .models import Libro


class LibroFilter(django_filters.FilterSet):
    """?categoria=ingenieria  ?año__gte=2020  ?disponible=true  ?autor=3  ?editorial=pearson"""

    categoria = django_filters.CharFilter(field_name="categoria__slug", lookup_expr="iexact")
    anio__gte = django_filters.NumberFilter(field_name="anio", lookup_expr="gte", label="Año desde")
    anio__lte = django_filters.NumberFilter(field_name="anio", lookup_expr="lte", label="Año hasta")
    disponible = django_filters.BooleanFilter(method="filtrar_disponible", label="Disponible")
    editorial = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Libro
        fields = ["categoria", "autor", "piso", "editorial"]

    def filtrar_disponible(self, queryset, nombre, valor):
        return queryset.filter(stock__gt=0) if valor else queryset.filter(stock=0)


# Alias con tilde que pide la guía: ?año__gte=2020 y ?año__lte=2024
LibroFilter.base_filters["año__gte"] = django_filters.NumberFilter(field_name="anio", lookup_expr="gte", label="Año desde")
LibroFilter.base_filters["año__lte"] = django_filters.NumberFilter(field_name="anio", lookup_expr="lte", label="Año hasta")


class OrdenamientoConAlias(OrderingFilter):
    """OrderingFilter que además acepta los nombres con tilde: ?ordering=-año, ?ordering=título."""

    ALIAS = {"año": "anio", "título": "titulo"}

    def get_ordering(self, request, queryset, view):
        parametro = request.query_params.get(self.ordering_param)
        if parametro:
            campos = []
            for campo in parametro.split(","):
                campo = campo.strip()
                signo = "-" if campo.startswith("-") else ""
                campos.append(signo + self.ALIAS.get(campo.lstrip("-"), campo.lstrip("-")))
            ordenamiento = self.remove_invalid_fields(queryset, campos, view, request)
            if ordenamiento:
                return ordenamiento
        return self.get_default_ordering(view)
