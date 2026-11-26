"""Throttling personalizado."""
from rest_framework.throttling import UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """Ráfagas: máx. 20 peticiones por minuto (anónimos por IP, usuarios por id). Evita scraping."""

    scope = "burst"
