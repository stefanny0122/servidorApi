"""
Modelos para procesamiento de imágenes individuales
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from database import Base


class ProcesamientoIndividual(Base):
    """
    Tabla para procesar imágenes individuales con transformaciones específicas
    """
    __tablename__ = "procesamientos_individuales"
    
    id_procesamiento = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, nullable=False, index=True)
    
    # Información del archivo
    nombre_original = Column(String(255), nullable=False)
    formato_original = Column(String(10), nullable=False)
    ruta_entrada = Column(Text, nullable=False)
    ruta_resultado = Column(Text)
    
    # Transformaciones específicas para esta imagen
    transformaciones = Column(JSON, nullable=False)  # Lista de transformaciones en JSON
    
    # Estado del procesamiento
    estado = Column(
        String(20), 
        default='pendiente',
        nullable=False,
        index=True
    )  # pendiente, procesando, completado, error
    
    # Metadatos
    tamanio_entrada_bytes = Column(Integer)
    tamanio_resultado_bytes = Column(Integer)
    formato_salida = Column(String(10))
    
    # Información del nodo que procesó
    id_nodo = Column(String(50))
    tiempo_procesamiento_segundos = Column(Integer)
    
    # Errores
    mensaje_error = Column(Text)
    
    # Timestamps
    fecha_creacion = Column(DateTime, default=func.now(), nullable=False)
    fecha_inicio_procesamiento = Column(DateTime)
    fecha_completado = Column(DateTime)
    
    def to_dict(self) -> dict:
        """Convierte el objeto a diccionario"""
        return {
            'id_procesamiento': self.id_procesamiento,
            'id_usuario': self.id_usuario,
            'nombre_original': self.nombre_original,
            'formato_original': self.formato_original,
            'ruta_resultado': self.ruta_resultado,
            'transformaciones': self.transformaciones,
            'estado': self.estado,
            'tamanio_entrada_kb': round(self.tamanio_entrada_bytes / 1024, 2) if self.tamanio_entrada_bytes else None,
            'tamanio_resultado_kb': round(self.tamanio_resultado_bytes / 1024, 2) if self.tamanio_resultado_bytes else None,
            'formato_salida': self.formato_salida,
            'id_nodo': self.id_nodo,
            'tiempo_procesamiento': self.tiempo_procesamiento_segundos,
            'mensaje_error': self.mensaje_error,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'fecha_completado': self.fecha_completado.isoformat() if self.fecha_completado else None
        }


class ProcesamientoIndividualCliente(Base):
    """
    Réplica en la base de datos del cliente
    """
    __tablename__ = "procesamientos_individuales_cliente"
    
    id_procesamiento = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, nullable=False, index=True)
    nombre_original = Column(String(255))
    formato_original = Column(String(10))
    ruta_resultado = Column(Text)
    estado = Column(String(20), default='pendiente')
    fecha_creacion = Column(DateTime, default=func.now())
    fecha_completado = Column(DateTime)