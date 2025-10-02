# filepath: d:\ServidorApi\models.py
from sqlalchemy import Column, Integer, String, DateTime
from database import Base

class LogSistema(Base):
    __tablename__ = "log_sistema"

    id = Column(Integer, primary_key=True, index=True)
    nivel = Column(String, nullable=False)
    mensaje = Column(String, nullable=False)
    fecha_hora = Column(DateTime, nullable=False)