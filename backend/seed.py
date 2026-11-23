from datetime import datetime, timedelta
from database import SessionLocal
import models

def poblar_datos():
    db = SessionLocal()
    if db.query(models.Usuario).first():
        db.close()
        return

    admin = models.Usuario(
        nombre="Dra. Marta Gómez (Admin)",
        cedula="52000111",
        celular="3001112233",
        facultad="Dirección Administrativa",
        tipo_vinculo="Administrativo",
        correo="admin@unimonserrate.edu.co",
        password="AdminUnimonserrate2026*",
        rol="admin"
    )
    guarda = models.Usuario(
        nombre="Carlos Ramírez (Guarda Turno A)",
        cedula="80111222",
        celular="3112223344",
        facultad="Seguridad Campus",
        tipo_vinculo="Administrativo",
        correo="guarda@unimonserrate.edu.co",
        password="GuardaTurno2026*",
        rol="guarda"
    )
    estudiante = models.Usuario(
        nombre="Camila Torres (Estudiante)",
        cedula="1010202030",
        celular="3203334455",
        facultad="Ingeniería de Sistemas",
        tipo_vinculo="Estudiante",
        correo="camila@unimonserrate.edu.co",
        password="Camila2026*",
        rol="conductor",
        mensualidad_activa=False
    )
    docente = models.Usuario(
        nombre="Prof. Andrés Silva (Docente)",
        cedula="79444555",
        celular="3154445566",
        facultad="Ciencias Administrativas",
        tipo_vinculo="Docente",
        correo="andres@unimonserrate.edu.co",
        password="Andres2026*",
        rol="conductor",
        mensualidad_activa=True,
        mensualidad_vence=datetime.now() + timedelta(days=25)
    )
    db.add_all([admin, guarda, estudiante, docente])
    db.commit()

    v1 = models.Vehiculo(placa="ABC-123", tipo="carro", usuario_id=estudiante.id)
    v2 = models.Vehiculo(placa="XYZ-98D", tipo="moto", usuario_id=estudiante.id)
    v3 = models.Vehiculo(placa="BIC-GW01", tipo="bicicleta", usuario_id=estudiante.id)
    v4 = models.Vehiculo(placa="KLM-456", tipo="carro", usuario_id=docente.id)
    db.add_all([v1, v2, v3, v4])

    t_carro = models.Tarifa(tipo_vehiculo="carro", fraccion_2h=7000, plena_mas_2h=12000, mensualidad=75000)
    t_moto = models.Tarifa(tipo_vehiculo="moto", fraccion_2h=5000, plena_mas_2h=9000, mensualidad=56000)
    t_bici = models.Tarifa(tipo_vehiculo="bicicleta", fraccion_2h=2000, plena_mas_2h=3500, mensualidad=20000)
    db.add_all([t_carro, t_moto, t_bici])

    bahias = []
    for i in range(1, 11):
        bahias.append(models.BahiaIoT(codigo=f"C-{i:02d}", tipo="carro", ocupada=(i <= 3), sensor_ok=True))
    for i in range(1, 11):
        bahias.append(models.BahiaIoT(codigo=f"M-{i:02d}", tipo="moto", ocupada=(i <= 2), sensor_ok=True))
    for i in range(1, 11):
        bahias.append(models.BahiaIoT(codigo=f"B-{i:02d}", tipo="bicicleta", ocupada=(i <= 1), sensor_ok=True))
    db.add_all(bahias)

    db.commit()
    db.close()
    print("Base de datos Unimonserrate (Seguridad Reforzada) poblada exitosamente.")