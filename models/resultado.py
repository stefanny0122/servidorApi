from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Resultado(Base):
    __tablename__ = "resultados"
    
    id_resultado = Column(Integer, primary_key=True, autoincrement=True)
    id_imagen = Column(Integer, ForeignKey('imagenes_servidor.id_imagen'))
    ruta_archivo = Column(Text)
    formato_salida = Column(String(10))
    tamaño_archivo = Column(Integer)
    fecha_creacion = Column(DateTime, default=func.now())