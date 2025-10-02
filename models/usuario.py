from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class UsuarioServidor(Base):
    __tablename__ = "usuarios_servidor"
    
    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    contraseña = Column(String(255), nullable=False)
    fecha_registro = Column(DateTime, default=func.now())
    ultimo_login = Column(DateTime)
    activo = Column(Integer, default=1)