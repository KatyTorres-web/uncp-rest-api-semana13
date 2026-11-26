"""Genera datos de prueba realistas para la API de la Biblioteca UNCP.

Uso:  python populate_data.py
Crea: 8 categorías, 30 autores, 50 libros, 12 usuarios (1 admin, 1 bibliotecario,
      10 lectores) y 30 préstamos (activos, devueltos y vencidos).
Es idempotente: se puede ejecutar varias veces sin duplicar datos.
"""
import os
import random
from datetime import timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.authtoken.models import Token  # noqa: E402

from biblioteca.models import Autor, Categoria, Libro, Perfil, Prestamo  # noqa: E402

User = get_user_model()
random.seed(13)
CLAVE = "Biblioteca2026!"

CATEGORIAS = [
    ("Ingeniería", "ingenieria"), ("Ciencias de la Computación", "computacion"),
    ("Matemáticas", "matematicas"), ("Física", "fisica"), ("Administración", "administracion"),
    ("Medicina", "medicina"), ("Literatura", "literatura"), ("Investigación", "investigacion"),
]

AUTORES = [
    ("Thomas H. Cormen", "Estadounidense", "Profesor de Dartmouth, coautor del clásico CLRS de algoritmos."),
    ("Robert C. Martin", "Estadounidense", "Ingeniero de software, autor de Clean Code y promotor de SOLID."),
    ("Andrew S. Tanenbaum", "Neerlandés-estadounidense", "Profesor emérito de la Vrije Universiteit, creador de MINIX."),
    ("Abraham Silberschatz", "Israelí-estadounidense", "Profesor de Yale, referente en sistemas operativos y bases de datos."),
    ("Ian Sommerville", "Británico", "Profesor de ingeniería de software en la Universidad de St Andrews."),
    ("Roger S. Pressman", "Estadounidense", "Consultor y autor de Ingeniería del Software: un enfoque práctico."),
    ("Martin Fowler", "Británico", "Científico jefe de ThoughtWorks, autor de Refactoring."),
    ("James F. Kurose", "Estadounidense", "Profesor de la Universidad de Massachusetts, redes de computadoras."),
    ("Stuart Russell", "Británico", "Profesor de Berkeley, coautor de Inteligencia Artificial: un enfoque moderno."),
    ("Ian Goodfellow", "Estadounidense", "Investigador en aprendizaje profundo, creador de las GAN."),
    ("James Stewart", "Canadiense", "Matemático, autor de la serie de Cálculo más usada en universidades."),
    ("Gilbert Strang", "Estadounidense", "Profesor del MIT, referente en álgebra lineal."),
    ("Ronald E. Walpole", "Estadounidense", "Estadístico, autor de Probabilidad y estadística para ingeniería."),
    ("Raymond A. Serway", "Estadounidense", "Físico, autor de Física para ciencias e ingeniería."),
    ("Hugh D. Young", "Estadounidense", "Profesor de Carnegie Mellon, coautor de Física Universitaria (Sears-Zemansky)."),
    ("Russell C. Hibbeler", "Estadounidense", "Ingeniero civil, autor de Mecánica de materiales y Estática."),
    ("Yunus A. Çengel", "Turco-estadounidense", "Profesor de termodinámica y transferencia de calor."),
    ("Stephen P. Robbins", "Estadounidense", "Autor de Administración y Comportamiento organizacional."),
    ("Philip Kotler", "Estadounidense", "Profesor de Kellogg, padre del marketing moderno."),
    ("Michael E. Porter", "Estadounidense", "Profesor de Harvard, creador de las cinco fuerzas competitivas."),
    ("Arthur C. Guyton", "Estadounidense", "Fisiólogo, autor del Tratado de fisiología médica."),
    ("Keith L. Moore", "Canadiense", "Anatomista, autor de Anatomía con orientación clínica."),
    ("Mario Vargas Llosa", "Peruana", "Premio Nobel de Literatura 2010."),
    ("César Vallejo", "Peruana", "Poeta peruano, autor de Los heraldos negros y Trilce."),
    ("José María Arguedas", "Peruana", "Escritor y antropólogo peruano, autor de Los ríos profundos."),
    ("Gabriel García Márquez", "Colombiana", "Premio Nobel de Literatura 1982."),
    ("Roberto Hernández Sampieri", "Mexicana", "Autor de Metodología de la investigación."),
    ("Mario Tamayo y Tamayo", "Colombiana", "Autor de El proceso de la investigación científica."),
    ("Erich Gamma", "Suiza", "Miembro del Gang of Four, autor de Patrones de diseño."),
    ("Ramez Elmasri", "Estadounidense", "Profesor de la Universidad de Texas, fundamentos de bases de datos."),
]

# (título, índice de autor, editorial, año, categoría)
LIBROS = [
    ("Introducción a los algoritmos", 0, "MIT Press", 2022, "computacion"),
    ("Clean Code", 1, "Prentice Hall", 2008, "computacion"),
    ("Clean Architecture", 1, "Prentice Hall", 2017, "computacion"),
    ("The Clean Coder", 1, "Prentice Hall", 2011, "computacion"),
    ("Sistemas operativos modernos", 2, "Pearson", 2015, "computacion"),
    ("Redes de computadoras", 2, "Pearson", 2021, "computacion"),
    ("Organización de computadoras", 2, "Pearson", 2013, "computacion"),
    ("Fundamentos de sistemas operativos", 3, "McGraw-Hill", 2018, "computacion"),
    ("Fundamentos de bases de datos", 3, "McGraw-Hill", 2020, "computacion"),
    ("Ingeniería de software", 4, "Pearson", 2016, "ingenieria"),
    ("Ingeniería del software: un enfoque práctico", 5, "McGraw-Hill", 2019, "ingenieria"),
    ("Refactoring", 6, "Addison-Wesley", 2018, "computacion"),
    ("Patterns of Enterprise Application Architecture", 6, "Addison-Wesley", 2002, "computacion"),
    ("Redes de computadoras: un enfoque descendente", 7, "Pearson", 2021, "computacion"),
    ("Inteligencia artificial: un enfoque moderno", 8, "Pearson", 2021, "computacion"),
    ("Deep Learning", 9, "MIT Press", 2016, "computacion"),
    ("Cálculo de una variable", 10, "Cengage", 2021, "matematicas"),
    ("Cálculo de varias variables", 10, "Cengage", 2021, "matematicas"),
    ("Precálculo", 10, "Cengage", 2017, "matematicas"),
    ("Álgebra lineal y sus aplicaciones", 11, "Cengage", 2016, "matematicas"),
    ("Introduction to Linear Algebra", 11, "Wellesley-Cambridge", 2023, "matematicas"),
    ("Probabilidad y estadística para ingeniería y ciencias", 12, "Pearson", 2012, "matematicas"),
    ("Física para ciencias e ingeniería Vol. 1", 13, "Cengage", 2019, "fisica"),
    ("Física para ciencias e ingeniería Vol. 2", 13, "Cengage", 2019, "fisica"),
    ("Física universitaria Vol. 1", 14, "Pearson", 2018, "fisica"),
    ("Física universitaria Vol. 2", 14, "Pearson", 2018, "fisica"),
    ("Mecánica de materiales", 15, "Pearson", 2017, "ingenieria"),
    ("Ingeniería mecánica: estática", 15, "Pearson", 2016, "ingenieria"),
    ("Ingeniería mecánica: dinámica", 15, "Pearson", 2016, "ingenieria"),
    ("Termodinámica", 16, "McGraw-Hill", 2019, "ingenieria"),
    ("Transferencia de calor y masa", 16, "McGraw-Hill", 2020, "ingenieria"),
    ("Mecánica de fluidos", 16, "McGraw-Hill", 2018, "ingenieria"),
    ("Administración", 17, "Pearson", 2018, "administracion"),
    ("Comportamiento organizacional", 17, "Pearson", 2019, "administracion"),
    ("Dirección de marketing", 18, "Pearson", 2016, "administracion"),
    ("Fundamentos de marketing", 18, "Pearson", 2017, "administracion"),
    ("Estrategia competitiva", 19, "Patria", 2015, "administracion"),
    ("Ventaja competitiva", 19, "Patria", 2015, "administracion"),
    ("Tratado de fisiología médica", 20, "Elsevier", 2021, "medicina"),
    ("Anatomía con orientación clínica", 21, "Wolters Kluwer", 2022, "medicina"),
    ("Embriología clínica", 21, "Elsevier", 2020, "medicina"),
    ("La ciudad y los perros", 22, "Alfaguara", 2012, "literatura"),
    ("Conversación en La Catedral", 22, "Alfaguara", 2010, "literatura"),
    ("Los heraldos negros", 23, "Peisa", 2018, "literatura"),
    ("Los ríos profundos", 24, "Peisa", 2011, "literatura"),
    ("Cien años de soledad", 25, "Sudamericana", 2017, "literatura"),
    ("Metodología de la investigación", 26, "McGraw-Hill", 2018, "investigacion"),
    ("El proceso de la investigación científica", 27, "Limusa", 2004, "investigacion"),
    ("Patrones de diseño", 28, "Addison-Wesley", 2003, "computacion"),
    ("Fundamentos de sistemas de bases de datos", 29, "Pearson", 2016, "computacion"),
]

# username, nombre, apellido, tipo, carrera
USUARIOS = [
    ("bibliotecario", "Rosa", "Quispe Huamán", "bibliotecario", "Biblioteca Central"),
    ("e.ramos", "Camilda", "Ramos Tacza", "estudiante", "Ingeniería de Sistemas"),
    ("e.torres", "Katherine", "Torres Ambrosio", "estudiante", "Ingeniería de Sistemas"),
    ("e.mendoza", "Luis", "Mendoza Rojas", "estudiante", "Ingeniería Civil"),
    ("e.paucar", "Diana", "Paucar Ccanto", "estudiante", "Ingeniería Mecánica"),
    ("e.huaman", "Jorge", "Huamán Poma", "estudiante", "Administración"),
    ("e.salazar", "Milagros", "Salazar Vílchez", "estudiante", "Medicina Humana"),
    ("d.castro", "Ricardo", "Castro Inga", "docente", "Ingeniería de Sistemas"),
    ("d.orellana", "Patricia", "Orellana Soto", "docente", "Matemática"),
    ("i.cardenas", "Víctor", "Cárdenas Lazo", "investigador", "Instituto de Investigación"),
    ("i.villanueva", "Elena", "Villanueva Rivera", "investigador", "Física"),
]


def isbn13(n):
    base = f"978612{n:06d}"
    suma = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    return f"{base}{(10 - suma % 10) % 10}"


@transaction.atomic
def poblar():
    # --- Usuarios ---
    admin, _ = User.objects.get_or_create(
        username="admin", defaults={"email": "biblioteca@uncp.edu.pe", "is_staff": True, "is_superuser": True,
                                    "first_name": "Jefe", "last_name": "de Biblioteca"}
    )
    admin.set_password("Admin2026!")
    admin.save()
    Perfil.objects.get_or_create(usuario=admin, defaults={"tipo": Perfil.Tipo.BIBLIOTECARIO, "carrera": "Dirección"})

    lectores = []
    for i, (username, nombre, apellido, tipo, carrera) in enumerate(USUARIOS):
        usuario, creado = User.objects.get_or_create(
            username=username,
            defaults={"first_name": nombre, "last_name": apellido, "email": f"{username}@uncp.edu.pe"},
        )
        if creado:
            usuario.set_password(CLAVE)
            usuario.save()
        Perfil.objects.update_or_create(
            usuario=usuario, defaults={"tipo": tipo, "carrera": carrera, "telefono": f"9{64000000 + i * 1371:08d}"}
        )
        if tipo != "bibliotecario":
            lectores.append(usuario)

    # --- Catálogo ---
    categorias = {slug: Categoria.objects.update_or_create(slug=slug, defaults={"nombre": nombre})[0]
                  for nombre, slug in CATEGORIAS}
    autores = [Autor.objects.update_or_create(nombre=n, defaults={"nacionalidad": nac, "biografia": bio})[0]
               for n, nac, bio in AUTORES]
    libros = []
    for i, (titulo, autor, editorial, anio, cat) in enumerate(LIBROS, start=1):
        libro, _ = Libro.objects.get_or_create(
            isbn=isbn13(i),
            defaults={
                "titulo": titulo, "autor": autores[autor], "editorial": editorial, "anio": anio,
                "categoria": categorias[cat], "stock": random.randint(1, 6) if i % 9 else 0,
                "estante": f"{'ABCDEFGH'[i % 8]}-{i:02d}", "piso": 1 + i % 3,
            },
        )
        libros.append(libro)

    # --- Préstamos (solo la primera vez) ---
    if not Prestamo.objects.exists():
        hoy = timezone.localdate()
        con_stock = [libro for libro in libros if libro.stock > 0]
        for n in range(30):
            usuario = lectores[n % len(lectores)]
            libro = con_stock[n % len(con_stock)]
            if n < 10:  # devueltos (algunos con retraso -> multa histórica)
                inicio = hoy - timedelta(days=60 - n)
                Prestamo.objects.create(usuario=usuario, libro=libro, fecha_prestamo=inicio,
                                        fecha_devolucion=inicio + timedelta(days=14),
                                        fecha_devuelto=inicio + timedelta(days=12 + n % 5),
                                        estado=Prestamo.Estado.DEVUELTO)
                continue
            if n < 18:  # vencidos: fecha límite en el pasado
                inicio = hoy - timedelta(days=20 + n)
                fin = inicio + timedelta(days=14)
            else:  # activos: vigentes
                inicio = hoy - timedelta(days=n % 10)
                fin = inicio + timedelta(days=14)
            Prestamo.objects.create(usuario=usuario, libro=libro, fecha_prestamo=inicio, fecha_devolucion=fin)
            libro.stock -= 1
            libro.save(update_fields=["stock"])
            if libro.stock == 0:
                con_stock.remove(libro)
        Prestamo.actualizar_vencidos()

    for usuario in User.objects.all():
        Token.objects.get_or_create(user=usuario)


if __name__ == "__main__":
    poblar()
    print("[OK] Datos de prueba generados")
    print(f"     Categorías: {Categoria.objects.count()} | Autores: {Autor.objects.count()} | "
          f"Libros: {Libro.objects.count()}")
    print(f"     Usuarios: {User.objects.count()} | Préstamos: {Prestamo.objects.count()} "
          f"(activos {Prestamo.objects.filter(estado='activo').count()}, "
          f"vencidos {Prestamo.objects.filter(estado='vencido').count()}, "
          f"devueltos {Prestamo.objects.filter(estado='devuelto').count()})")
    print("     admin / Admin2026!  |  bibliotecario y lectores / Biblioteca2026!")
