from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class UsuarioCliente(Base):
    __tablename__ = "usuarios_cliente"
    
    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    contraseña = Column(String(255), nullable=False)
    fecha_registro = Column(DateTime, default=func.now())
    ultimo_login = Column(DateTime)
    activo = Column(Integer, default=1)

class SolicitudCliente(Base):
    __tablename__ = "solicitudes_cliente"
    
    id_solicitud = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, nullable=False)
    estado = Column(String(20), default='pendiente')
    fecha_envio = Column(DateTime, default=func.now())
    fecha_completado = Column(DateTime)

class ImagenCliente(Base):
    __tablename__ = "imagenes_cliente"
    
    id_imagen = Column(Integer, primary_key=True, autoincrement=True)
    id_solicitud = Column(Integer, nullable=False)
    nombre_original = Column(String(255))
    formato_original = Column(String(10))
    ruta_origen = Column(Text)
    ruta_resultado = Column(Text)
    estado = Column(String(20), default='procesando')
    fecha_procesado = Column(DateTime)