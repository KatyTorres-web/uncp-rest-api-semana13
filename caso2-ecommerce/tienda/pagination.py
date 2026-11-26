"""Paginaciones de la API."""
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination


class PaginacionCatalogo(PageNumberPagination):
    """Catálogo: 24 por página (?page=2), el cliente puede pedir hasta 100 (?page_size=48)."""

    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 100


class PaginacionOrdenes(LimitOffsetPagination):
    """Órdenes: LimitOffset de 50 (?limit=50&offset=100)."""

    default_limit = 50
    max_limit = 200
