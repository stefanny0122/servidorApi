from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base

class LogSistema(Base):
    __tablename__ = "logs_sistema"   

    id_log = Column(Integer, primary_key=True, index=True)
    nivel = Column(String(20), nullable=False)       
    mensaje = Column(Text, nullable=False)            
    modulo = Column(String(100), nullable=False)     
    fecha_hora = Column(DateTime, nullable=False)    
