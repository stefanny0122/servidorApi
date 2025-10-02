from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class ImagenServidor(Base):
    __tablename__ = "imagenes_servidor"
    
    id_imagen = Column(Integer, primary_key=True, autoincrement=True)
    id_solicitud = Column(Integer, ForeignKey('solicitudes_servidor.id_solicitud'))
    nombre_original = Column(String(255))
    formato_original = Column(String(10))
    ruta_origen = Column(Text)
    ruta_resultado = Column(Text)
    estado = Column(String(20), default='procesando')
    fecha_procesado = Column(DateTime)