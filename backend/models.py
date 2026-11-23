from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    cedula = Column(String, default="1000000000")
    celular = Column(String, default="3000000000")
    facultad = Column(String, default="Ingeniería")
    tipo_vinculo = Column(String, default="Estudiante")  # Estudiante, Docente, Administrativo
    correo = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    rol = Column(String, default="conductor")  # conductor, guarda, admin
    mensualidad_activa = Column(Boolean, default=False)
    mensualidad_vence = Column(DateTime, nullable=True)
    vehiculos = relationship("Vehiculo", back_populates="propietario")

class Vehiculo(Base):
    __tablename__ = "vehiculos"
    id = Column(Integer, primary_key=True, index=True)
    placa = Column(String, unique=True, index=True, nullable=False)
    tipo = Column(String, nullable=False)  # carro, moto
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    propietario = relationship("Usuario", back_populates="vehiculos")

class Tarifa(Base):
    __tablename__ = "tarifas"
    id = Column(Integer, primary_key=True, index=True)
    tipo_vehiculo = Column(String, nullable=False)
    fraccion_2h = Column(Float, nullable=False)
    plena_mas_2h = Column(Float, nullable=False)
    mensualidad = Column(Float, nullable=False)
    fecha_actualizacion = Column(DateTime, default=datetime.now)

class RegistroAcceso(Base):
    __tablename__ = "registros_acceso"
    id = Column(Integer, primary_key=True, index=True)
    placa = Column(String, index=True, nullable=False)
    tipo_vehiculo = Column(String, nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    es_invitado = Column(Boolean, default=False)
    invitado_nombre = Column(String, nullable=True)
    invitado_cedula = Column(String, nullable=True)
    invitado_celular = Column(String, nullable=True)
    invitado_destino = Column(String, nullable=True)
    metodo_entrada = Column(String, default="QR")
    hora_entrada = Column(DateTime, default=datetime.now)
    hora_salida = Column(DateTime, nullable=True)
    valor_cobrado = Column(Float, default=0.0)
    estado = Column(String, default="ADENTRO")

class BahiaIoT(Base):
    __tablename__ = "bahias_iot"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, nullable=False)
    tipo = Column(String, nullable=False)
    ocupada = Column(Boolean, default=False)
    sensor_ok = Column(Boolean, default=True)
    ultima_senal = Column(DateTime, default=datetime.now)