import re
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import engine, get_db
from seed import poblar_datos

models.Base.metadata.create_all(bind=engine)
poblar_datos()

app = FastAPI(title="Parqueadero Unimonserrate API", version="4.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "CLAVE_SECRETA_UNIMONSERATE_2026"
ALGORITHM = "HS256"
LLAVE_MAESTRA_IOT = "IOT-UNIMONSERRATE-99"

class LoginReq(BaseModel):
    correo: str
    password: str
    codigo_seguridad: Optional[str] = None

class RegistroReq(BaseModel):
    nombre: str
    cedula: str = "1020304050"
    celular: str = "3100000000"
    facultad: str = "Ingeniería"
    tipo_vinculo: str = "Estudiante"
    correo: str
    password: str

class VehiculoReq(BaseModel):
    usuario_id: int
    placa: str
    tipo: str

class PagoMensualidadReq(BaseModel):
    usuario_id: int
    metodo_pago: str

class EscanerQRReq(BaseModel):
    token_qr: str

class InvitadoReq(BaseModel):
    placa: str
    tipo_vehiculo: str
    nombre: str
    cedula: str
    celular: str
    destino: str

class SalidaManualReq(BaseModel):
    placa: str

class TarifaUpdateReq(BaseModel):
    tipo_vehiculo: str
    fraccion_2h: float
    plena_mas_2h: float
    mensualidad: float

class IoTBahiaReq(BaseModel):
    codigo: str
    ocupada: bool
    sensor_ok: bool = True
    llave_iot: str

class LPRLecturaReq(BaseModel):
    placa: str
    llave_iot: str

def validar_identificador_vehiculo(placa: str, tipo: str) -> bool:
    placa = placa.upper().strip()
    if tipo == "carro":
        return bool(re.match(r"^[A-Z]{3}-?[0-9]{3}$", placa))
    elif tipo == "moto":
        return bool(re.match(r"^[A-Z]{3}-?[0-9]{2}[A-Z]$", placa))
    elif tipo == "bicicleta":
        return len(placa) >= 4
    return False

def calcular_cobro(db: Session, registro: models.RegistroAcceso, usuario: Optional[models.Usuario]):
    if registro.tipo_vehiculo == "bicicleta" and usuario is not None:
        return 0.0
    if usuario and usuario.mensualidad_activa and usuario.mensualidad_vence and usuario.mensualidad_vence > datetime.now():
        return 0.0
    tarifa = db.query(models.Tarifa).filter(
        models.Tarifa.tipo_vehiculo == registro.tipo_vehiculo
    ).order_by(models.Tarifa.id.desc()).first()
    if not tarifa:
        defaults = {"carro": 7000.0, "moto": 5000.0, "bicicleta": 2000.0}
        return defaults.get(registro.tipo_vehiculo, 7000.0)
    duracion_horas = (datetime.now() - registro.hora_entrada).total_seconds() / 3600.0
    return float(tarifa.fraccion_2h if duracion_horas <= 2.0 else tarifa.plena_mas_2h)

def sincronizar_bahia_iot(db: Session, tipo_vehiculo: str, ocupar: bool):
    bahia = db.query(models.BahiaIoT).filter(
        models.BahiaIoT.tipo == tipo_vehiculo,
        models.BahiaIoT.sensor_ok == True,
        models.BahiaIoT.ocupada == (not ocupar)
    ).first()
    if bahia:
        bahia.ocupada = ocupar
        bahia.ultima_senal = datetime.now()
        return bahia.codigo
    return None

@app.post("/api/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.correo == req.correo.strip(), models.Usuario.password == req.password).first()
    if not user:
        raise HTTPException(status_code=401, detail="Correo institucional o contraseña incorrectos.")
    if user.rol == "admin":
        if req.codigo_seguridad != "2026":
            raise HTTPException(status_code=403, detail="PIN de seguridad administrativo inválido.")
    if user.rol == "guarda":
        if req.codigo_seguridad != "8844":
            raise HTTPException(status_code=403, detail="Código de Turno de Portería inválido. Solo personal autorizado en turno.")
    return {
        "id": user.id, "nombre": user.nombre, "correo": user.correo,
        "rol": user.rol, "mensualidad_activa": user.mensualidad_activa,
        "mensualidad_vence": user.mensualidad_vence
    }

@app.post("/api/registro")
def registrar_usuario(req: RegistroReq, db: Session = Depends(get_db)):
    if db.query(models.Usuario).filter(models.Usuario.correo == req.correo.strip()).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    nuevo = models.Usuario(
        nombre=req.nombre, cedula=req.cedula, celular=req.celular,
        facultad=req.facultad, tipo_vinculo=req.tipo_vinculo,
        correo=req.correo.strip(), password=req.password, rol="conductor"
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"mensaje": "Usuario registrado exitosamente en Unimonserrate", "usuario_id": nuevo.id}

@app.get("/api/usuario/{usuario_id}")
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    vehiculos = [{"id": v.id, "placa": v.placa, "tipo": v.tipo} for v in user.vehiculos]
    historial = db.query(models.RegistroAcceso).filter(models.RegistroAcceso.usuario_id == usuario_id).order_by(models.RegistroAcceso.id.desc()).all()
    return {
        "id": user.id, "nombre": user.nombre, "facultad": user.facultad,
        "tipo_vinculo": user.tipo_vinculo, "rol": user.rol,
        "mensualidad_activa": user.mensualidad_activa,
        "mensualidad_vence": user.mensualidad_vence,
        "vehiculos": vehiculos, "historial": historial
    }

@app.post("/api/vehiculos")
def agregar_vehiculo(req: VehiculoReq, db: Session = Depends(get_db)):
    placa_limpia = req.placa.upper().strip()
    if req.tipo in ["carro", "moto"] and "-" not in placa_limpia and len(placa_limpia) == 6:
        placa_limpia = f"{placa_limpia[:3]}-{placa_limpia[3:]}"
    if not validar_identificador_vehiculo(placa_limpia, req.tipo):
        raise HTTPException(status_code=400, detail="Formato inválido (Carro: ABC-123 | Moto: ABC-12D | Bici: Serial mín. 4 caracteres)")
    if db.query(models.Vehiculo).filter(models.Vehiculo.placa == placa_limpia).first():
        raise HTTPException(status_code=400, detail="Esta placa o serial de bicicleta ya está registrado")
    v = models.Vehiculo(placa=placa_limpia, tipo=req.tipo, usuario_id=req.usuario_id)
    db.add(v)
    db.commit()
    return {"mensaje": f"Vehículo/Bicicleta {placa_limpia} registrado correctamente"}

@app.post("/api/pagar-mensualidad")
def pagar_mensualidad(req: PagoMensualidadReq, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.id == req.usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.mensualidad_activa = True
    user.mensualidad_vence = datetime.now() + timedelta(days=30)
    db.commit()
    return {"mensaje": f"Transacción aprobada vía {req.metodo_pago}. Pase libre activo por 30 días.", "vence": user.mensualidad_vence}

@app.get("/api/qr/{usuario_id}/{placa}")
def generar_qr_dinamico(usuario_id: int, placa: str, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    vehiculo = db.query(models.Vehiculo).filter(models.Vehiculo.placa == placa, models.Vehiculo.usuario_id == usuario_id).first()
    if not user or not vehiculo:
        raise HTTPException(status_code=404, detail="Usuario o vehículo no válido")
    expiracion = datetime.utcnow() + timedelta(seconds=60)
    payload = {
        "tipo_qr": "UNIMONSERATE",
        "uid": user.id,
        "nombre": user.nombre,
        "placa": vehiculo.placa,
        "tipo": vehiculo.tipo,
        "exp": expiracion
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"token_qr": token, "expira_en_segundos": 60, "placa": vehiculo.placa}

@app.post("/api/porteria/escanear-qr")
def escanear_qr(req: EscanerQRReq, db: Session = Depends(get_db)):
    if req.token_qr.startswith("INVITADO:"):
        placa = req.token_qr.split(":")[1].strip().upper()
        activo = db.query(models.RegistroAcceso).filter(models.RegistroAcceso.placa == placa, models.RegistroAcceso.estado == "ADENTRO").first()
        if not activo:
            raise HTTPException(status_code=404, detail="El ticket de invitado ya fue liquidado o no existe.")
        cobro = calcular_cobro(db, activo, None)
        activo.hora_salida = datetime.now()
        activo.valor_cobrado = cobro
        activo.estado = "FINALIZADO"
        sincronizar_bahia_iot(db, activo.tipo_vehiculo, ocupar=False)
        db.commit()
        minutos = max(1, int((activo.hora_salida - activo.hora_entrada).total_seconds() / 60))
        return {
            "accion": "SALIDA",
            "talanquera": "ABIERTA",
            "conductor": f"Visitante: {activo.invitado_nombre}",
            "placa": placa,
            "tiempo_minutos": minutos,
            "valor_a_cobrar": cobro,
            "mensualidad": False
        }

    try:
        datos = jwt.decode(req.token_qr, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="CÓDIGO QR EXPIRADO (>60s). Solicite al conductor actualizar su pantalla.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Código QR inválido o adulterado.")

    uid = datos["uid"]
    placa = datos["placa"]
    tipo = datos["tipo"]
    user = db.query(models.Usuario).filter(models.Usuario.id == uid).first()

    activo_mismo = db.query(models.RegistroAcceso).filter(
        models.RegistroAcceso.placa == placa,
        models.RegistroAcceso.estado == "ADENTRO"
    ).first()

    if activo_mismo:
        cobro = calcular_cobro(db, activo_mismo, user)
        activo_mismo.hora_salida = datetime.now()
        activo_mismo.valor_cobrado = cobro
        activo_mismo.estado = "FINALIZADO"
        sincronizar_bahia_iot(db, tipo, ocupar=False)
        db.commit()
        minutos = max(1, int((activo_mismo.hora_salida - activo_mismo.hora_entrada).total_seconds() / 60))
        return {
            "accion": "SALIDA",
            "talanquera": "ABIERTA",
            "conductor": user.nombre,
            "placa": placa,
            "tiempo_minutos": minutos,
            "valor_a_cobrar": cobro,
            "mensualidad": (user.mensualidad_activa or tipo == "bicicleta")
        }

    otro_adentro = db.query(models.RegistroAcceso).filter(
        models.RegistroAcceso.usuario_id == uid,
        models.RegistroAcceso.estado == "ADENTRO"
    ).first()
    if otro_adentro:
        raise HTTPException(status_code=400, detail=f"Acceso denegado: El usuario ya tiene {otro_adentro.placa} dentro del campus.")

    bahia_asignada = sincronizar_bahia_iot(db, tipo, ocupar=True)
    nuevo_acceso = models.RegistroAcceso(
        placa=placa, tipo_vehiculo=tipo, usuario_id=uid, es_invitado=False, metodo_entrada="QR"
    )
    db.add(nuevo_acceso)
    db.commit()
    return {
        "accion": "ENTRADA",
        "talanquera": "ABIERTA",
        "conductor": user.nombre,
        "placa": placa,
        "tipo": tipo,
        "bahia": bahia_asignada or "Zona General",
        "mensualidad": (user.mensualidad_activa or tipo == "bicicleta")
    }

@app.post("/api/porteria/invitado")
def registrar_invitado(req: InvitadoReq, db: Session = Depends(get_db)):
    placa_limpia = req.placa.upper().strip()
    if req.tipo_vehiculo in ["carro", "moto"] and "-" not in placa_limpia and len(placa_limpia) == 6:
        placa_limpia = f"{placa_limpia[:3]}-{placa_limpia[3:]}"
    if not validar_identificador_vehiculo(placa_limpia, req.tipo_vehiculo):
        raise HTTPException(status_code=400, detail="Identificador inválido (Carro: ABC-123 | Moto: ABC-12D | Bici: Serial)")
    if db.query(models.RegistroAcceso).filter(models.RegistroAcceso.placa == placa_limpia, models.RegistroAcceso.estado == "ADENTRO").first():
        raise HTTPException(status_code=400, detail="Este vehículo visitante ya se encuentra adentro.")
    sincronizar_bahia_iot(db, req.tipo_vehiculo, ocupar=True)
    acceso = models.RegistroAcceso(
        placa=placa_limpia, tipo_vehiculo=req.tipo_vehiculo, es_invitado=True,
        invitado_nombre=req.nombre, invitado_cedula=req.cedula,
        invitado_celular=req.celular, invitado_destino=req.destino,
        metodo_entrada="MANUAL_INVITADO"
    )
    db.add(acceso)
    db.commit()
    db.refresh(acceso)
    return {
        "mensaje": f"Visitante {req.nombre} ({placa_limpia}) ingresado — TALANQUERA DE ENTRADA ABIERTA",
        "talanquera": "ABIERTA",
        "ticket_id": acceso.id,
        "placa": placa_limpia,
        "qr_invitado": f"INVITADO:{placa_limpia}",
        "nombre": req.nombre,
        "celular": req.celular,
        "destino": req.destino
    }

@app.post("/api/porteria/salida-placa")
def salida_por_placa(req: SalidaManualReq, db: Session = Depends(get_db)):
    placa_limpia = req.placa.upper().strip()
    activo = db.query(models.RegistroAcceso).filter(models.RegistroAcceso.placa == placa_limpia, models.RegistroAcceso.estado == "ADENTRO").first()
    if not activo:
        raise HTTPException(status_code=404, detail="No hay registro activo adentro para esta placa.")
    user = db.query(models.Usuario).filter(models.Usuario.id == activo.usuario_id).first() if activo.usuario_id else None
    cobro = calcular_cobro(db, activo, user)
    activo.hora_salida = datetime.now()
    activo.valor_cobrado = cobro
    activo.estado = "FINALIZADO"
    sincronizar_bahia_iot(db, activo.tipo_vehiculo, ocupar=False)
    db.commit()
    minutos = max(1, int((activo.hora_salida - activo.hora_entrada).total_seconds() / 60))
    return {
        "accion": "SALIDA",
        "talanquera": "ABIERTA",
        "conductor": f"Visitante: {activo.invitado_nombre}" if activo.es_invitado else user.nombre,
        "placa": placa_limpia,
        "tiempo_minutos": minutos,
        "valor_a_cobrar": cobro,
        "mensualidad": False if activo.es_invitado else (user.mensualidad_activa or activo.tipo_vehiculo == "bicicleta")
    }

@app.get("/api/porteria/activos")
def vehiculos_adentro(db: Session = Depends(get_db)):
    adentro = db.query(models.RegistroAcceso).filter(models.RegistroAcceso.estado == "ADENTRO").all()
    total_inscritos = db.query(models.Vehiculo).count()
    return {"adentro": adentro, "total_inscritos": total_inscritos}

@app.get("/api/iot/estado")
def estado_bahias(db: Session = Depends(get_db)):
    bahias = db.query(models.BahiaIoT).all()
    return {
        "carros_libres": sum(1 for b in bahias if b.tipo == "carro" and not b.ocupada and b.sensor_ok),
        "carros_total": sum(1 for b in bahias if b.tipo == "carro"),
        "motos_libres": sum(1 for b in bahias if b.tipo == "moto" and not b.ocupada and b.sensor_ok),
        "motos_total": sum(1 for b in bahias if b.tipo == "moto"),
        "bicis_libres": sum(1 for b in bahias if b.tipo == "bicicleta" and not b.ocupada and b.sensor_ok),
        "bicis_total": sum(1 for b in bahias if b.tipo == "bicicleta"),
        "bahias": bahias
    }

@app.post("/api/iot/sensor")
def actualizar_sensor(req: IoTBahiaReq, db: Session = Depends(get_db)):
    if req.llave_iot != LLAVE_MAESTRA_IOT:
        raise HTTPException(status_code=403, detail="Llave maestra de hardware IoT inválida. Acceso bloqueado.")
    bahia = db.query(models.BahiaIoT).filter(models.BahiaIoT.codigo == req.codigo).first()
    if not bahia:
        raise HTTPException(status_code=404, detail="Bahía no encontrada")
    bahia.ocupada = req.ocupada
    bahia.sensor_ok = req.sensor_ok
    bahia.ultima_senal = datetime.now()
    db.commit()
    return {"mensaje": f"Sensor {req.codigo} actualizado"}

@app.post("/api/lpr/lectura")
def lectura_camara_lpr(req: LPRLecturaReq, db: Session = Depends(get_db)):
    if req.llave_iot != LLAVE_MAESTRA_IOT:
        raise HTTPException(status_code=403, detail="Llave de control de talanquera LPR inválida. Operación denegada.")
    placa = req.placa.upper().strip()
    vehiculo = db.query(models.Vehiculo).filter(models.Vehiculo.placa == placa).first()
    if not vehiculo:
        return {"talanquera": "CERRADA", "motivo": "Placa no registrada. Debe intervenir el guarda."}
    user = vehiculo.propietario
    if not (user.mensualidad_activa and user.mensualidad_vence and user.mensualidad_vence > datetime.now()):
        return {"talanquera": "CERRADA", "motivo": f"Usuario {user.nombre} sin mensualidad activa. Use QR."}
    if db.query(models.RegistroAcceso).filter(models.RegistroAcceso.usuario_id == user.id, models.RegistroAcceso.estado == "ADENTRO").first():
        return {"talanquera": "CERRADA", "motivo": "El usuario ya tiene un vehículo adentro."}
    sincronizar_bahia_iot(db, vehiculo.tipo, ocupar=True)
    acceso = models.RegistroAcceso(placa=placa, tipo_vehiculo=vehiculo.tipo, usuario_id=user.id, metodo_entrada="LPR")
    db.add(acceso)
    db.commit()
    return {"talanquera": "ABIERTA", "motivo": f"Bienvenido {user.nombre}. Foto LPR guardada."}

@app.get("/api/admin/tarifas")
def obtener_tarifas(db: Session = Depends(get_db)):
    t_carro = db.query(models.Tarifa).filter(models.Tarifa.tipo_vehiculo == "carro").order_by(models.Tarifa.id.desc()).first()
    t_moto = db.query(models.Tarifa).filter(models.Tarifa.tipo_vehiculo == "moto").order_by(models.Tarifa.id.desc()).first()
    t_bici = db.query(models.Tarifa).filter(models.Tarifa.tipo_vehiculo == "bicicleta").order_by(models.Tarifa.id.desc()).first()
    historial = db.query(models.Tarifa).order_by(models.Tarifa.id.desc()).limit(10).all()
    return {"carro": t_carro, "moto": t_moto, "bicicleta": t_bici, "historial": historial}

@app.post("/api/admin/tarifas")
def actualizar_tarifa(req: TarifaUpdateReq, db: Session = Depends(get_db)):
    nueva = models.Tarifa(
        tipo_vehiculo=req.tipo_vehiculo,
        fraccion_2h=req.fraccion_2h,
        plena_mas_2h=req.plena_mas_2h,
        mensualidad=req.mensualidad
    )
    db.add(nueva)
    db.commit()
    return {"mensaje": f"Tarifa de {req.tipo_vehiculo.upper()} actualizada correctamente"}

@app.get("/api/admin/usuarios")
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(models.Usuario).all()

@app.put("/api/admin/usuarios/{usuario_id}/rol")
def cambiar_rol(usuario_id: int, nuevo_rol: str, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.rol = nuevo_rol
    db.commit()
    return {"mensaje": f"Rol de {user.nombre} actualizado a {nuevo_rol}"}

app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")