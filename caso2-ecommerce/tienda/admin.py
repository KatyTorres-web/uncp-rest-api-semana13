from django.contrib import admin

from .models import Carrito, Categoria, Cupon, ImagenProducto, ItemOrden, Orden, Perfil, Producto, Resena


class ImagenInline(admin.TabularInline):
    model = ImagenProducto
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("sku", "nombre", "marca", "categoria", "precio", "descuento", "stock", "vendedor")
    list_filter = ("categoria", "marca")
    search_fields = ("sku", "nombre", "marca")
    inlines = [ImagenInline]


class ItemOrdenInline(admin.TabularInline):
    model = ItemOrden
    extra = 0


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ("numero", "usuario", "estado", "total", "metodo_pago", "fecha_creacion")
    list_filter = ("estado", "metodo_pago")
    inlines = [ItemOrdenInline]


admin.site.register([Categoria, Perfil, Cupon, Carrito, Resena])
