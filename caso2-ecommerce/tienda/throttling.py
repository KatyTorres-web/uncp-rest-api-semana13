"""Throttling personalizado de TecnoMarket."""
from rest_framework.throttling import UserRateThrottle


class CheckoutRateThrottle(UserRateThrottle):
    """Máx. 10 checkouts por hora por usuario (evita abuso de checkout)."""

    scope = "checkout"


class SearchRateThrottle(UserRateThrottle):
    """Máx. 100 búsquedas (?search=) por hora: evita el scraping de precios."""

    scope = "search"

    def allow_request(self, request, view):
        if not request.query_params.get("search"):
            return True  # solo cuenta las peticiones de búsqueda
        return super().allow_request(request, view)
