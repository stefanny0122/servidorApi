import logging
import sys
import os
from datetime import datetime
from database import get_db_servidor
from models import LogSistema


# Configuración global de logging
def setup_logging():
    """Configuración centralizada del logging"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Formato consistente
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] [%(threadName)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remover handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Handler para archivo
    log_file = f"logs/servidor_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """Retorna un logger configurado con el nombre especificado"""
    return logging.getLogger(name)

class DatabaseLogHandler(logging.Handler):
    """Handler personalizado para guardar logs en base de datos"""
    
    def emit(self, record):
        try:
            log_entry = LogSistema(
                nivel=record.levelname.lower(),
                mensaje=self.format(record),
                modulo=record.name,
                fecha_hora=datetime.now()
            )
            
            with get_db_servidor() as db:
                db.add(log_entry)
                
        except Exception as e:
            # Fallback a consola si hay error con la BD
            print(f"Error guardando log en BD: {e}")

# Configurar al importar el