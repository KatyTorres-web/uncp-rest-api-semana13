"""Manejador de excepciones: registra en logs cada petición bloqueada por throttling (429)."""
import logging

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler

logger = logging.getLogger("api.throttling")


def manejador_con_logs(exc, context):
    respuesta = exception_handler(exc, context)
    if isinstance(exc, Throttled):
        request = context["request"]
        usuario = request.user.username if request.user.is_authenticated else "anonimo"
        logger.warning(
            "429 %s %s usuario=%s ip=%s espera=%ss",
            request.method, request.get_full_path(), usuario, request.META.get("REMOTE_ADDR"), exc.wait and int(exc.wait),
        )
    return respuesta
