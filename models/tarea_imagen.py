from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class TareaImagen(Base):
    __tablename__ = "tarea_imagen"
    
    id_tarea = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_imagen = Column(Integer, ForeignKey("imagenservidor.id_imagen"), nullable=False)
    id_nodo = Column(Integer, ForeignKey("nodo.id_nodo"), nullable=True)
    estado = Column(Enum('pendiente', 'procesando', 'completada', 'fallida', 'cancelada'), default='pendiente')
    transformaciones_aplicadas = Column(JSON, nullable=True) 
    fecha_inicio = Column(DateTime, nullable=True)
    fecha_fin = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
     
    imagen = relationship("ImagenServidor", backref="tareas")
    nodo = relationship("Nodo", backref="tareas")