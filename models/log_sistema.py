# filepath: d:\ServidorApi\models.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base

class LogSistema(Base):
    __tablename__ = "logs_sistema"   # ojo: en tu BD se llama logs_sistema

    id_log = Column(Integer, primary_key=True, index=True)
    nivel = Column(String(20), nullable=False)       # VARCHAR(20)
    mensaje = Column(Text, nullable=False)           # TEXT
    modulo = Column(String(100), nullable=False)     # VARCHAR(100)
    fecha_hora = Column(DateTime, nullable=False)    # DATETIME
