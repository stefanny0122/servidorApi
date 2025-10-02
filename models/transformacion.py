from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Transformacion(Base):
    __tablename__ = "transformaciones"
    
    id_transformacion = Column(Integer, primary_key=True, autoincrement=True)
    id_imagen = Column(Integer, ForeignKey('imagenes_servidor.id_imagen'))
    tipo = Column(String(50), nullable=False)
    parametros = Column(Text)  # JSON como string
    orden = Column(Integer, default=0)
    fecha_creacion = Column(DateTime, default=func.now())