import os
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime
from database import get_db_servidor
from models.imagen import ImagenServidor
from models.resultado import Resultado
from config import config
from utils.logger import get_logger

logger = get_logger("ServicioAlmacenamiento")

class ServicioAlmacenamiento:
    def __init__(self):
        self.base_dir = config.upload_dir
        self.results_dir = config.results_dir
    
    def guardar_imagen_temporal(self, file_content: bytes, filename: str) -> str:
        """Guarda una imagen temporalmente antes del procesamiento"""
        try: 
            os.makedirs(self.base_dir, exist_ok=True)
             
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            file_path = os.path.join(self.base_dir, unique_filename)
             
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            logger.info(f"Imagen guardada temporalmente: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error guardando imagen temporal: {e}")
            raise
    
    def guardar_resultado(self, imagen_procesada, id_imagen: int, formato: str) -> str:
        """Guarda la imagen procesada en el directorio de resultados"""
        try:
 
            os.makedirs(self.results_dir, exist_ok=True)
             
            filename = f"resultado_{id_imagen}.{formato.lower()}"
            file_path = os.path.join(self.results_dir, filename)
             
            imagen_procesada.save(file_path, format=formato.upper())
             
            with get_db_servidor() as db:
                resultado = Resultado(
                    id_imagen=id_imagen,
                    ruta_archivo=file_path,
                    formato_salida=formato,
                    tamaño_archivo=os.path.getsize(file_path)
                )
                db.add(resultado)
            
            logger.info(f"Resultado guardado: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error guardando resultado: {e}")
            raise
    
    def obtener_ruta_resultado(self, id_imagen: int) -> Optional[str]:
        """Obtiene la ruta del resultado procesado de una imagen"""
        try:
            with get_db_servidor() as db:
                resultado = db.query(Resultado).filter(Resultado.id_imagen == id_imagen).first()
                return resultado.ruta_archivo if resultado else None
        except Exception as e:
            logger.error(f"Error obteniendo ruta resultado: {e}")
            return None
    
    def limpiar_archivos_temporales(self, horas: int = 24):
        """Limpia archivos temporales más antiguos que X horas"""
        try:
            current_time = datetime.now().timestamp()
            for filename in os.listdir(self.base_dir):
                file_path = os.path.join(self.base_dir, filename)
                if os.path.isfile(file_path):
      
                    file_time = os.path.getctime(file_path)
                    if (current_time - file_time) > (horas * 3600):
                        os.remove(file_path)
                        logger.info(f"Archivo temporal eliminado: {filename}")
        except Exception as e:
            logger.error(f"Error limpiando archivos temporales: {e}")
    
    def crear_zip_lote(self, id_solicitud: int) -> str:
        """Crea un archivo ZIP con todos los resultados de una solicitud"""
        import zipfile
        
        try:
            with get_db_servidor() as db:
 
                imagenes = db.query(ImagenServidor).filter(
                    ImagenServidor.id_solicitud == id_solicitud,
                    ImagenServidor.estado == 'procesada'
                ).all()
             
            zip_path = os.path.join(self.results_dir, f"lote_{id_solicitud}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for imagen in imagenes:
                    resultado = self.obtener_ruta_resultado(imagen.id_imagen)
                    if resultado and os.path.exists(resultado):
 
                        zipf.write(resultado, f"{imagen.nombre_original}")
            
            logger.info(f"ZIP creado para lote {id_solicitud}: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Error creando ZIP para lote {id_solicitud}: {e}")
            raise