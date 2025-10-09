from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class Nodo(Base):
    __tablename__ = "nodos"
    
    id_nodo = Column(Integer, primary_key=True, autoincrement=True)
    ip = Column(String(45), nullable=False)  
    descripcion = Column(Text)
    capacidad_total = Column(Integer, default=10)
    capacidad_usada = Column(Integer, default=0)
    estado = Column(String(20), default='activo')  
    fecha_registro = Column(DateTime, default=func.now())
    ultima_actualizacion = Column(DateTime, default=func.now(), onupdate=func.now())