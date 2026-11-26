"""Pruebas unitarias de la API de la biblioteca.  Ejecutar: python manage.py test"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Autor, Categoria, Libro, Perfil, Prestamo


class BibliotecaAPITest(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia los contadores de throttling
        self.autor = Autor.objects.create(nombre="Robert C. Martin", nacionalidad="Estadounidense")
        self.cat = Categoria.objects.create(nombre="Ingeniería", slug="ingenieria")
        self.libro = Libro.objects.create(isbn="9780132350884", titulo="Clean Code", autor=self.autor,
                                          editorial="Prentice Hall", anio=2008, categoria=self.cat,
                                          stock=2, estante="A-1", piso=1)
        self.bibliotecario = User.objects.create_user("bib", password="x")
        Perfil.objects.create(usuario=self.bibliotecario, tipo=Perfil.Tipo.BIBLIOTECARIO)
        self.estudiante = User.objects.create_user("est", password="x")
        Perfil.objects.create(usuario=self.estudiante, tipo=Perfil.Tipo.ESTUDIANTE)

    def autenticar(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_catalogo_publico_con_campos_calculados(self):
        r = self.client.get("/api/libros/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        libro = r.data["results"][0]
        self.assertTrue(libro["disponible"])
        self.assertEqual(libro["autor"]["nombre"], "Robert C. Martin")  # nested
        self.assertIn("/api/libros/", libro["url"])  # HATEOAS

    def test_filtro_por_categoria_y_anio(self):
        r = self.client.get("/api/libros/?categoria=ingenieria&año__gte=2020")
        self.assertEqual(r.data["count"], 0)
        r = self.client.get("/api/libros/?categoria=ingenieria&anio__gte=2000")
        self.assertEqual(r.data["count"], 1)

    def test_estudiante_no_puede_crear_libros(self):
        self.autenticar(self.estudiante)
        r = self.client.post("/api/libros/", {"titulo": "X"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_prestamo_descuenta_y_devolucion_repone_stock(self):
        self.autenticar(self.bibliotecario)
        r = self.client.post("/api/prestamos/", {"usuario": self.estudiante.pk, "libro": self.libro.pk}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.libro.refresh_from_db()
        self.assertEqual(self.libro.stock, 1)
        r = self.client.post(f"/api/prestamos/{r.data['id']}/devolver/")
        self.assertEqual(r.data["estado"], "devuelto")
        self.libro.refresh_from_db()
        self.assertEqual(self.libro.stock, 2)

    def test_limite_de_cinco_prestamos(self):
        for _ in range(5):
            Prestamo.objects.create(usuario=self.estudiante, libro=self.libro)
        self.autenticar(self.bibliotecario)
        r = self.client.post("/api/prestamos/", {"usuario": self.estudiante.pk, "libro": self.libro.pk}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_multa_por_retraso(self):
        hace_20 = timezone.localdate() - timedelta(days=20)
        p = Prestamo.objects.create(usuario=self.estudiante, libro=self.libro, fecha_prestamo=hace_20,
                                    fecha_devolucion=hace_20 + timedelta(days=14))
        self.assertEqual(p.multa, 12)  # 6 días x S/ 2.00

    def test_perfil_requiere_autenticacion(self):
        self.assertEqual(self.client.get("/api/usuarios/perfil/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.autenticar(self.estudiante)
        r = self.client.get("/api/usuarios/perfil/")
        self.assertEqual(r.data["username"], "est")
