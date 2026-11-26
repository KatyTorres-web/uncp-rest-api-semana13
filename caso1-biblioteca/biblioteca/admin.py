from django.contrib import admin

from .models import Autor, Categoria, Libro, Perfil, Prestamo


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "anio", "categoria", "stock", "piso", "estante")
    list_filter = ("categoria", "piso")
    search_fields = ("titulo", "isbn", "autor__nombre")


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ("libro", "usuario", "fecha_prestamo", "fecha_devolucion", "estado")
    list_filter = ("estado",)


admin.site.register([Autor, Categoria, Perfil])
