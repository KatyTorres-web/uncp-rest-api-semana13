"""Autenticación por token con expiración (requisito de seguridad)."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class TokenConExpiracion(TokenAuthentication):
    """Igual que TokenAuthentication, pero el token caduca a las N horas."""

    def authenticate_credentials(self, key):
        usuario, token = super().authenticate_credentials(key)
        limite = token.created + timedelta(hours=settings.TOKEN_EXPIRACION_HORAS)
        if timezone.now() > limite:
            token.delete()
            raise AuthenticationFailed("El token expiró. Solicite uno nuevo en /api/auth/token/.")
        return usuario, token
