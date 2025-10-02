from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class SolicitudServidor(Base):
    __tablename__ = "solicitudes_servidor"
    
    id_solicitud = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, nullable=False)
    estado = Column(String(20), default='procesando')
    fecha_envio = Column(DateTime, default=func.now())
    fecha_completado = Column(DateTime)