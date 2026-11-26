"""Pruebas unitarias de la API de TecnoMarket.  Ejecutar: python manage.py test"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Categoria, Orden, Perfil, Producto


class TecnoMarketAPITest(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia los contadores de throttling
        self.vendedor = User.objects.create_user("vend", password="x")
        Perfil.objects.create(usuario=self.vendedor, rol=Perfil.Rol.VENDEDOR, nombre_tienda="Tienda Test")
        self.cliente = User.objects.create_user("cli", password="x")
        Perfil.objects.create(usuario=self.cliente)
        self.cat = Categoria.objects.create(nombre="Laptops", slug="laptops")
        self.producto = Producto.objects.create(
            sku="LAP-001", nombre="Dell G15 Gaming", marca="Dell", categoria=self.cat, vendedor=self.vendedor,
            precio=Decimal("1000.00"), descuento=10, stock=5, especificaciones={"ram": "16 GB"},
        )

    def autenticar(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_catalogo_publico_con_calculados_y_filtros(self):
        r = self.client.get("/api/productos/?categoria=laptops&marca=dell&precio_min=500&disponible=true")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        producto = r.data["results"][0]
        self.assertEqual(producto["precio_con_descuento"], "900.00")
        self.assertEqual(producto["categoria"]["slug"], "laptops")  # nested
        self.assertTrue(producto["disponible"])

    def test_cliente_no_puede_publicar(self):
        self.autenticar(self.cliente)
        self.assertEqual(self.client.post("/api/productos/", {}, format="json").status_code, status.HTTP_403_FORBIDDEN)

    def test_no_se_puede_agregar_mas_que_el_stock(self):
        self.autenticar(self.cliente)
        r = self.client.post("/api/carrito/agregar/", {"producto": self.producto.pk, "cantidad": 6}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_crea_orden_con_snapshot_y_descuenta_stock(self):
        self.autenticar(self.cliente)
        self.client.post("/api/carrito/agregar/", {"producto": self.producto.pk, "cantidad": 2}, format="json")
        r = self.client.post("/api/carrito/checkout/", {"direccion_envio": "Huancayo", "metodo_pago": "culqi"},
                             format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["items"][0]["precio_unitario"], "900.00")
        self.assertEqual(r.data["total"], "2124.00")  # 1800 + 18 % IGV
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 3)
        # El precio cambia después, pero la orden conserva el precio de compra
        self.producto.precio = Decimal("2000")
        self.producto.save()
        orden = self.client.get(f"/api/ordenes/{r.data['id']}/")
        self.assertEqual(orden.data["items"][0]["precio_unitario"], "900.00")

    def test_resena_solo_para_compradores(self):
        self.autenticar(self.cliente)
        datos = {"producto": self.producto.pk, "calificacion": 5, "titulo": "Excelente"}
        self.assertEqual(self.client.post("/api/reseñas/", datos, format="json").status_code,
                         status.HTTP_403_FORBIDDEN)
        self.client.post("/api/carrito/agregar/", {"producto": self.producto.pk}, format="json")
        r = self.client.post("/api/carrito/checkout/", {"direccion_envio": "Huancayo", "metodo_pago": "niubiz"},
                             format="json")
        Orden.objects.filter(pk=r.data["id"]).update(estado=Orden.Estado.PAGADA)
        r = self.client.post("/api/reseñas/", datos, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertTrue(r.data["es_compra_verificada"])

    def test_flujo_de_estados_y_cancelacion(self):
        self.autenticar(self.cliente)
        self.client.post("/api/carrito/agregar/", {"producto": self.producto.pk}, format="json")
        orden = self.client.post("/api/carrito/checkout/", {"direccion_envio": "Lima", "metodo_pago": "culqi"},
                                 format="json").data
        r = self.client.post(f"/api/ordenes/{orden['id']}/cancelar/")
        self.assertEqual(r.data["estado"], "cancelada")
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 5)  # stock repuesto
        self.autenticar(self.vendedor)
        r = self.client.patch(f"/api/ordenes/{orden['id']}/", {"estado": "pagada"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)  # cancelada es estado final
