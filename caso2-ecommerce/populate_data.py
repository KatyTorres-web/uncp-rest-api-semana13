"""Genera datos de prueba realistas para la API de TecnoMarket Perú.

Uso:  python populate_data.py
Crea: 5 categorías, 100 productos (con imágenes y especificaciones JSON), 21 usuarios
      (1 admin, 4 vendedores, 16 clientes), 2 cupones, 50 órdenes y 100 reseñas verificadas.
Es idempotente: si ya hay órdenes, no las vuelve a crear.
"""
import os
import random
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402
from django.db.models import F  # noqa: E402
from rest_framework.authtoken.models import Token  # noqa: E402

from tienda.models import (  # noqa: E402
    IGV, Categoria, Cupon, ImagenProducto, ItemOrden, Orden, Perfil, Producto, Resena, redondear,
)

User = get_user_model()
random.seed(2026)
CLAVE = "Tecno2026!"

CATEGORIAS = [
    ("Laptops", "laptops", "Laptops para trabajo, estudio y gaming"),
    ("Smartphones", "smartphones", "Celulares Android y iPhone"),
    ("Componentes", "componentes", "Tarjetas de video, procesadores, memorias y almacenamiento"),
    ("Accesorios", "accesorios", "Periféricos, audio y cargadores"),
    ("Monitores", "monitores", "Monitores para oficina, diseño y gaming"),
]

# Por categoría: (marca, modelo, precio base, especificaciones)
CATALOGO = {
    "laptops": [
        ("Dell", "G15 Gaming RTX 4060", 4299, {"procesador": "Intel Core i7-13650HX", "ram": "16 GB", "gpu": "RTX 4060"}),
        ("Dell", "Inspiron 15 3530", 2399, {"procesador": "Intel Core i5-1335U", "ram": "8 GB", "almacenamiento": "512 GB SSD"}),
        ("Dell", "XPS 13 Plus", 6899, {"procesador": "Intel Core i7-1360P", "ram": "16 GB", "pantalla": "13.4\" OLED"}),
        ("HP", "Victus 15 Gaming", 3599, {"procesador": "AMD Ryzen 7 7840HS", "ram": "16 GB", "gpu": "RTX 4050"}),
        ("HP", "Pavilion 14", 2799, {"procesador": "Intel Core i5-1335U", "ram": "16 GB", "almacenamiento": "512 GB SSD"}),
        ("HP", "Omen 16 Gaming", 5999, {"procesador": "Intel Core i9-13900HX", "ram": "32 GB", "gpu": "RTX 4070"}),
        ("Lenovo", "IdeaPad Slim 3", 1999, {"procesador": "AMD Ryzen 5 7520U", "ram": "8 GB", "almacenamiento": "512 GB SSD"}),
        ("Lenovo", "Legion 5 Pro Gaming", 5499, {"procesador": "AMD Ryzen 7 7745HX", "ram": "16 GB", "gpu": "RTX 4060"}),
        ("Lenovo", "ThinkPad E14", 3299, {"procesador": "Intel Core i7-1355U", "ram": "16 GB", "uso": "Empresarial"}),
        ("Asus", "TUF Gaming F15", 3899, {"procesador": "Intel Core i7-12700H", "ram": "16 GB", "gpu": "RTX 4050"}),
        ("Asus", "Vivobook 15", 2199, {"procesador": "Intel Core i5-1235U", "ram": "8 GB", "almacenamiento": "512 GB SSD"}),
        ("Asus", "ROG Strix G16 Gaming", 6499, {"procesador": "Intel Core i9-13980HX", "ram": "32 GB", "gpu": "RTX 4070"}),
        ("Acer", "Nitro V 15 Gaming", 3199, {"procesador": "Intel Core i5-13420H", "ram": "16 GB", "gpu": "RTX 4050"}),
        ("Acer", "Aspire 5", 2299, {"procesador": "Intel Core i5-1335U", "ram": "8 GB", "almacenamiento": "512 GB SSD"}),
        ("Apple", "MacBook Air M2", 4599, {"procesador": "Apple M2", "ram": "8 GB", "almacenamiento": "256 GB SSD"}),
        ("Apple", "MacBook Air M3 15\"", 5899, {"procesador": "Apple M3", "ram": "16 GB", "almacenamiento": "512 GB SSD"}),
        ("Apple", "MacBook Pro 14 M3 Pro", 8999, {"procesador": "Apple M3 Pro", "ram": "18 GB", "almacenamiento": "512 GB SSD"}),
        ("MSI", "Katana 15 Gaming", 4199, {"procesador": "Intel Core i7-13620H", "ram": "16 GB", "gpu": "RTX 4060"}),
        ("MSI", "Modern 14", 1899, {"procesador": "Intel Core i5-1235U", "ram": "8 GB", "almacenamiento": "512 GB SSD"}),
        ("Huawei", "MateBook D16", 2899, {"procesador": "Intel Core i5-12450H", "ram": "16 GB", "pantalla": "16\" IPS"}),
    ],
    "smartphones": [
        ("Samsung", "Galaxy S24 Ultra 256 GB", 5299, {"pantalla": "6.8\" AMOLED", "camara": "200 MP", "bateria": "5000 mAh"}),
        ("Samsung", "Galaxy S24 128 GB", 3499, {"pantalla": "6.2\" AMOLED", "camara": "50 MP", "bateria": "4000 mAh"}),
        ("Samsung", "Galaxy A55 5G", 1699, {"pantalla": "6.6\" AMOLED", "camara": "50 MP", "bateria": "5000 mAh"}),
        ("Samsung", "Galaxy A35 5G", 1299, {"pantalla": "6.6\" AMOLED", "camara": "50 MP", "bateria": "5000 mAh"}),
        ("Samsung", "Galaxy A15", 699, {"pantalla": "6.5\" AMOLED", "camara": "50 MP", "bateria": "5000 mAh"}),
        ("Apple", "iPhone 15 128 GB", 3999, {"pantalla": "6.1\" OLED", "chip": "A16 Bionic", "camara": "48 MP"}),
        ("Apple", "iPhone 15 Pro Max 256 GB", 6299, {"pantalla": "6.7\" OLED", "chip": "A17 Pro", "camara": "48 MP"}),
        ("Apple", "iPhone 14 128 GB", 3199, {"pantalla": "6.1\" OLED", "chip": "A15 Bionic", "camara": "12 MP"}),
        ("Apple", "iPhone 13 128 GB", 2599, {"pantalla": "6.1\" OLED", "chip": "A15 Bionic", "camara": "12 MP"}),
        ("Xiaomi", "Redmi Note 13 Pro", 1199, {"pantalla": "6.67\" AMOLED", "camara": "200 MP", "bateria": "5100 mAh"}),
        ("Xiaomi", "Redmi Note 13", 849, {"pantalla": "6.67\" AMOLED", "camara": "108 MP", "bateria": "5000 mAh"}),
        ("Xiaomi", "Xiaomi 14", 3699, {"pantalla": "6.36\" AMOLED", "camara": "50 MP Leica", "bateria": "4610 mAh"}),
        ("Xiaomi", "Poco X6 Pro", 1399, {"pantalla": "6.67\" AMOLED", "chip": "Dimensity 8300", "bateria": "5000 mAh"}),
        ("Motorola", "Edge 50 Pro", 1999, {"pantalla": "6.7\" pOLED", "camara": "50 MP", "carga": "125 W"}),
        ("Motorola", "Moto G84 5G", 999, {"pantalla": "6.55\" pOLED", "camara": "50 MP", "bateria": "5000 mAh"}),
        ("Motorola", "Moto G54 5G", 799, {"pantalla": "6.5\" IPS", "camara": "50 MP", "bateria": "5000 mAh"}),
        ("Honor", "Magic 6 Lite", 1299, {"pantalla": "6.78\" AMOLED", "camara": "108 MP", "bateria": "5300 mAh"}),
        ("Honor", "X8b", 899, {"pantalla": "6.7\" AMOLED", "camara": "108 MP", "bateria": "4500 mAh"}),
        ("Google", "Pixel 8", 2999, {"pantalla": "6.2\" OLED", "chip": "Tensor G3", "camara": "50 MP"}),
        ("Oppo", "Reno 11 5G", 1599, {"pantalla": "6.7\" AMOLED", "camara": "50 MP", "carga": "67 W"}),
    ],
    "componentes": [
        ("Nvidia", "GeForce RTX 4060 8 GB", 1399, {"memoria": "8 GB GDDR6", "tdp": "115 W"}),
        ("Nvidia", "GeForce RTX 4070 Super 12 GB", 2999, {"memoria": "12 GB GDDR6X", "tdp": "220 W"}),
        ("Nvidia", "GeForce RTX 4090 24 GB", 8999, {"memoria": "24 GB GDDR6X", "tdp": "450 W"}),
        ("AMD", "Radeon RX 7600 8 GB", 1199, {"memoria": "8 GB GDDR6", "tdp": "165 W"}),
        ("AMD", "Radeon RX 7800 XT 16 GB", 2499, {"memoria": "16 GB GDDR6", "tdp": "263 W"}),
        ("AMD", "Ryzen 5 7600X", 999, {"nucleos": 6, "hilos": 12, "socket": "AM5"}),
        ("AMD", "Ryzen 7 7800X3D", 1899, {"nucleos": 8, "hilos": 16, "socket": "AM5"}),
        ("AMD", "Ryzen 9 7950X", 2599, {"nucleos": 16, "hilos": 32, "socket": "AM5"}),
        ("Intel", "Core i5-14600K", 1299, {"nucleos": 14, "hilos": 20, "socket": "LGA1700"}),
        ("Intel", "Core i7-14700K", 1799, {"nucleos": 20, "hilos": 28, "socket": "LGA1700"}),
        ("Intel", "Core i9-14900K", 2499, {"nucleos": 24, "hilos": 32, "socket": "LGA1700"}),
        ("Kingston", "Fury Beast 16 GB DDR5 5600", 299, {"tipo": "DDR5", "capacidad": "16 GB"}),
        ("Kingston", "NV2 1 TB NVMe", 269, {"tipo": "SSD NVMe PCIe 4.0", "capacidad": "1 TB"}),
        ("Corsair", "Vengeance 32 GB DDR5 6000", 549, {"tipo": "DDR5", "capacidad": "2 x 16 GB"}),
        ("Corsair", "RM850e Fuente 850 W", 499, {"potencia": "850 W", "certificacion": "80 Plus Gold"}),
        ("Samsung", "990 Pro 2 TB NVMe", 899, {"tipo": "SSD NVMe PCIe 4.0", "capacidad": "2 TB"}),
        ("Samsung", "870 EVO 1 TB SATA", 399, {"tipo": "SSD SATA", "capacidad": "1 TB"}),
        ("Asus", "TUF Gaming B650-Plus", 899, {"socket": "AM5", "formato": "ATX"}),
        ("MSI", "MAG B760 Tomahawk", 949, {"socket": "LGA1700", "formato": "ATX"}),
        ("Western Digital", "WD Blue 2 TB HDD", 289, {"tipo": "HDD 7200 rpm", "capacidad": "2 TB"}),
    ],
    "accesorios": [
        ("Logitech", "G502 Hero Mouse Gaming", 199, {"dpi": 25600, "conexion": "USB"}),
        ("Logitech", "MX Master 3S", 449, {"dpi": 8000, "conexion": "Bluetooth"}),
        ("Logitech", "G Pro X Superlight 2", 599, {"peso": "60 g", "conexion": "Inalámbrico"}),
        ("Logitech", "K380 Teclado Bluetooth", 149, {"conexion": "Bluetooth", "dispositivos": 3}),
        ("Razer", "BlackWidow V4 Teclado Mecánico", 699, {"switches": "Green", "rgb": True}),
        ("Razer", "DeathAdder V3 Mouse Gaming", 349, {"dpi": 30000, "peso": "59 g"}),
        ("Redragon", "Kumara K552 Teclado Mecánico", 159, {"switches": "Blue", "formato": "TKL"}),
        ("HyperX", "Cloud II Audífonos Gaming", 399, {"sonido": "7.1 virtual", "conexion": "USB / 3.5 mm"}),
        ("HyperX", "Cloud Alpha Wireless", 799, {"bateria": "300 h", "conexion": "Inalámbrico"}),
        ("Sony", "WH-1000XM5 Audífonos", 1499, {"cancelacion_ruido": True, "bateria": "30 h"}),
        ("JBL", "Flip 6 Parlante Bluetooth", 499, {"resistencia": "IP67", "bateria": "12 h"}),
        ("JBL", "Tune 520BT Audífonos", 199, {"bateria": "57 h", "conexion": "Bluetooth 5.3"}),
        ("Apple", "AirPods Pro 2", 1199, {"cancelacion_ruido": True, "estuche": "USB-C"}),
        ("Samsung", "Galaxy Buds2 Pro", 699, {"cancelacion_ruido": True, "bateria": "29 h"}),
        ("Anker", "PowerCore 20000 mAh", 199, {"capacidad": "20000 mAh", "carga": "20 W"}),
        ("Anker", "Cargador GaN 65 W", 229, {"potencia": "65 W", "puertos": 3}),
        ("TP-Link", "Archer AX55 Router WiFi 6", 349, {"wifi": "WiFi 6", "velocidad": "AX3000"}),
        ("TP-Link", "Deco X20 Mesh (2 unid.)", 699, {"wifi": "WiFi 6", "cobertura": "370 m2"}),
        ("Logitech", "C920 Webcam Full HD", 329, {"resolucion": "1080p", "microfono": "Estéreo"}),
        ("Xiaomi", "Smart Band 8", 179, {"pantalla": "1.62\" AMOLED", "bateria": "16 días"}),
    ],
    "monitores": [
        ("LG", "UltraGear 27GP850 27\" QHD 165 Hz", 1599, {"resolucion": "2560x1440", "hz": 165, "panel": "Nano IPS"}),
        ("LG", "27UL500 27\" 4K", 1299, {"resolucion": "3840x2160", "hz": 60, "panel": "IPS"}),
        ("LG", "24MP400 24\" Full HD", 499, {"resolucion": "1920x1080", "hz": 75, "panel": "IPS"}),
        ("Samsung", "Odyssey G5 32\" Curvo", 1299, {"resolucion": "2560x1440", "hz": 165, "panel": "VA"}),
        ("Samsung", "Odyssey G7 28\" 4K", 2699, {"resolucion": "3840x2160", "hz": 144, "panel": "IPS"}),
        ("Samsung", "T35F 24\" Full HD", 449, {"resolucion": "1920x1080", "hz": 75, "panel": "IPS"}),
        ("Samsung", "ViewFinity S8 27\" 4K", 1899, {"resolucion": "3840x2160", "hz": 60, "panel": "IPS"}),
        ("Asus", "TUF VG249Q1A 24\" 165 Hz", 699, {"resolucion": "1920x1080", "hz": 165, "panel": "IPS"}),
        ("Asus", "ROG Swift PG27AQDM OLED", 4499, {"resolucion": "2560x1440", "hz": 240, "panel": "OLED"}),
        ("Asus", "ProArt PA278QV 27\"", 1499, {"resolucion": "2560x1440", "hz": 75, "uso": "Diseño"}),
        ("Dell", "P2423H 24\" Full HD", 799, {"resolucion": "1920x1080", "hz": 60, "uso": "Oficina"}),
        ("Dell", "S2721DGF 27\" QHD 165 Hz", 1499, {"resolucion": "2560x1440", "hz": 165, "panel": "IPS"}),
        ("Dell", "UltraSharp U2723QE 4K", 2799, {"resolucion": "3840x2160", "hz": 60, "uso": "Diseño"}),
        ("AOC", "24G2 24\" 144 Hz", 649, {"resolucion": "1920x1080", "hz": 144, "panel": "IPS"}),
        ("AOC", "C27G2 27\" Curvo 165 Hz", 899, {"resolucion": "1920x1080", "hz": 165, "panel": "VA"}),
        ("BenQ", "Zowie XL2546K 240 Hz", 2299, {"resolucion": "1920x1080", "hz": 240, "uso": "eSports"}),
        ("BenQ", "GW2480 24\" Eye-Care", 499, {"resolucion": "1920x1080", "hz": 60, "panel": "IPS"}),
        ("MSI", "G274F 27\" 180 Hz", 849, {"resolucion": "1920x1080", "hz": 180, "panel": "IPS"}),
        ("Gigabyte", "M27Q 27\" QHD 170 Hz", 1199, {"resolucion": "2560x1440", "hz": 170, "panel": "IPS"}),
        ("ViewSonic", "VX2479 24\" Full HD", 459, {"resolucion": "1920x1080", "hz": 100, "panel": "IPS"}),
    ],
}

VENDEDORES = [("v.techstore", "TechStore Lima"), ("v.gamerzone", "GamerZone Perú"),
              ("v.compuandina", "CompuAndina Huancayo"), ("v.movilplus", "MovilPlus")]
CLIENTES = [
    ("c.ramos", "Camilda", "Ramos Tacza", "Huancayo"), ("c.torres", "Katherine", "Torres Ambrosio", "Huancayo"),
    ("c.quispe", "Jorge", "Quispe Mamani", "Cusco"), ("c.flores", "María", "Flores Ríos", "Lima"),
    ("c.garcia", "Luis", "García Vega", "Arequipa"), ("c.rojas", "Ana", "Rojas Paredes", "Trujillo"),
    ("c.huaman", "Carlos", "Huamán Ccori", "Huancayo"), ("c.chavez", "Lucía", "Chávez Soto", "Lima"),
    ("c.mendoza", "Pedro", "Mendoza Salas", "Piura"), ("c.vargas", "Rosa", "Vargas León", "Ica"),
    ("c.castillo", "Diego", "Castillo Núñez", "Lima"), ("c.ramirez", "Sofía", "Ramírez Cruz", "Chiclayo"),
    ("c.espinoza", "Miguel", "Espinoza Lara", "Huancayo"), ("c.salazar", "Valeria", "Salazar Ruiz", "Tacna"),
    ("c.paucar", "Jhon", "Paucar Inga", "Jauja"), ("c.medina", "Fiorella", "Medina Torres", "Lima"),
]
TITULOS = {5: ["Excelente compra", "Superó mis expectativas", "Muy recomendado"],
           4: ["Muy bueno", "Buena relación calidad-precio", "Cumple lo prometido"],
           3: ["Está bien", "Cumple, pero nada más"],
           2: ["Esperaba más", "Regular"],
           1: ["No lo recomiendo"]}
COMENTARIOS = ["Llegó en 3 días a {ciudad}, bien embalado.", "Funciona tal cual la descripción.",
               "Buen rendimiento para el precio.", "La atención del vendedor fue rápida.",
               "Lo uso todos los días para la universidad.", "El envío demoró un poco más de lo indicado."]


def crear_usuario(username, nombre, apellido, rol, **perfil):
    usuario, creado = User.objects.get_or_create(
        username=username, defaults={"first_name": nombre, "last_name": apellido, "email": f"{username}@correo.pe"}
    )
    if creado:
        usuario.set_password(CLAVE)
        usuario.save()
    Perfil.objects.update_or_create(usuario=usuario, defaults={"rol": rol, **perfil})
    return usuario


@transaction.atomic
def poblar():
    admin, _ = User.objects.get_or_create(username="admin", defaults={
        "is_staff": True, "is_superuser": True, "email": "admin@tecnomarket.pe", "first_name": "Owner"})
    admin.set_password("Admin2026!")
    admin.save()
    Perfil.objects.get_or_create(usuario=admin)

    vendedores = [crear_usuario(u, tienda, "", "vendedor", nombre_tienda=tienda, telefono="014567890")
                  for u, tienda in VENDEDORES]
    clientes = [crear_usuario(u, n, a, "cliente", direccion=f"Av. Principal 123, {c}", telefono=f"9{i:08d}")
                for i, (u, n, a, c) in enumerate(CLIENTES, start=11223344)]

    categorias = {}
    for nombre, slug, desc in CATEGORIAS:
        categorias[slug], _ = Categoria.objects.update_or_create(
            slug=slug, defaults={"nombre": nombre, "descripcion": desc,
                                 "imagen": f"https://cdn.tecnomarket.pe/categorias/{slug}.jpg"})

    productos = []
    for slug, items in CATALOGO.items():
        for n, (marca, modelo, precio, specs) in enumerate(items, start=1):
            sku = f"{slug[:3].upper()}-{marca[:4].upper().replace(' ', '')}-{n:03d}"
            producto, creado = Producto.objects.get_or_create(sku=sku, defaults={
                "nombre": f"{marca} {modelo}", "marca": marca, "categoria": categorias[slug],
                "descripcion": f"{marca} {modelo}. Garantía oficial de 12 meses en Perú.",
                "vendedor": vendedores[(n + len(slug)) % len(vendedores)],
                "precio": Decimal(precio), "descuento": random.choice([0, 0, 0, 5, 10, 15, 20]),
                "stock": random.choice([0, 3, 8, 15, 25, 40, 60]) + 10, "especificaciones": specs,
            })
            if creado:
                ImagenProducto.objects.bulk_create([
                    ImagenProducto(producto=producto, url=f"https://cdn.tecnomarket.pe/productos/{sku.lower()}-{i}.jpg",
                                   orden=i) for i in range(1, 4)])
            productos.append(producto)
    # Algunos productos agotados para probar ?disponible=false
    Producto.objects.filter(sku__in=[p.sku for p in productos[9::20]]).update(stock=0)

    Cupon.objects.get_or_create(codigo="TECNO10", defaults={"porcentaje": 10})
    Cupon.objects.get_or_create(codigo="CYBERWOW20", defaults={"porcentaje": 20})

    if not Orden.objects.exists():
        estados = (["entregada"] * 22 + ["enviada"] * 10 + ["pagada"] * 8 + ["pendiente"] * 6 + ["cancelada"] * 4)
        con_stock = [p for p in Producto.objects.filter(stock__gt=5)]
        for n, estado in enumerate(estados):
            cliente = clientes[n % len(clientes)]
            elegidos = random.sample(con_stock, random.randint(2, 4))
            lineas = [(p, random.randint(1, 2)) for p in elegidos]
            subtotal = redondear(sum(p.precio_con_descuento * c for p, c in lineas))
            orden = Orden.objects.create(
                usuario=cliente, direccion_envio=cliente.perfil.direccion,
                metodo_pago=random.choice(Orden.MetodoPago.values), estado=estado, subtotal=subtotal,
                impuestos=redondear(subtotal * IGV), total=redondear(subtotal * (1 + IGV)),
                numero_seguimiento=f"OLV-{n:08d}" if estado in ("enviada", "entregada") else "",
            )
            for p, cantidad in lineas:
                ItemOrden.objects.create(orden=orden, producto=p, vendedor=p.vendedor, sku=p.sku,
                                         nombre_producto=p.nombre, precio_unitario=p.precio_con_descuento,
                                         cantidad=cantidad)
                if estado != "cancelada":
                    Producto.objects.filter(pk=p.pk).update(stock=F("stock") - cantidad)

        # Reseñas solo de compras verificadas (orden pagada, enviada o entregada)
        compras = list(ItemOrden.objects.filter(orden__estado__in=["pagada", "enviada", "entregada"])
                       .values_list("orden__usuario_id", "producto_id").distinct())
        random.shuffle(compras)
        for usuario_id, producto_id in compras[:100]:
            nota = random.choices([5, 4, 3, 2, 1], weights=[45, 30, 13, 8, 4])[0]
            usuario = User.objects.get(pk=usuario_id)
            Resena.objects.create(
                usuario=usuario, producto_id=producto_id, calificacion=nota, titulo=random.choice(TITULOS[nota]),
                comentario=random.choice(COMENTARIOS).format(ciudad=usuario.perfil.direccion.split(", ")[-1]),
            )

    for usuario in User.objects.all():
        Token.objects.get_or_create(user=usuario)


if __name__ == "__main__":
    poblar()
    print("[OK] Datos de prueba generados")
    print(f"     Categorías: {Categoria.objects.count()} | Productos: {Producto.objects.count()} | "
          f"Usuarios: {User.objects.count()}")
    print(f"     Órdenes: {Orden.objects.count()} | Reseñas: {Resena.objects.count()} | "
          f"Cupones: {Cupon.objects.count()}")
    print("     admin / Admin2026!  |  vendedores (v.*) y clientes (c.*) / Tecno2026!")
