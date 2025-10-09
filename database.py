from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config import config
import logging

logger = logging.getLogger("Database")
 
engine_servidor = create_engine(
    config.get_db_url("servidor"),
    pool_size=config.db_servidor.pool_size,
    max_overflow=config.db_servidor.max_overflow,
    echo=config.debug,
    pool_pre_ping=True
)

engine_cliente = create_engine(
    config.get_db_url("cliente"),
    pool_size=config.db_cliente.pool_size,
    max_overflow=config.db_cliente.max_overflow,
    echo=config.debug,
    pool_pre_ping=True
)
 
SessionServidor = sessionmaker(bind=engine_servidor)
SessionCliente = sessionmaker(bind=engine_cliente)

Base = declarative_base()
 
from models.usuario import UsuarioServidor
from models.cliente_models import UsuarioCliente
from models.lote_procesamiento import SolicitudServidor
from models.imagen import ImagenServidor
from models.transformacion import Transformacion
from models.resultado import Resultado
from models.nodo import Nodo
from models.log_sistema import LogSistema

def init_db():
    """Inicializa las tablas en la base de datos"""
    try: 
        Base.metadata.create_all(bind=engine_servidor)
        logger.info("Tablas de servidor creadas/inicializadas")
         
        Base.metadata.create_all(bind=engine_cliente)
        logger.info("Tablas de cliente creadas/inicializadas")
        
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        raise

@contextmanager
def get_db_servidor() -> Session:
    """Context manager para obtener sesión de base de datos del servidor"""
    db = SessionServidor()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error en transacción servidor: {str(e)}")
        raise
    finally:
        db.close()

@contextmanager
def get_db_cliente() -> Session:
    """Context manager para obtener sesión de base de datos del cliente"""
    db = SessionCliente()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error en transacción cliente: {str(e)}")
        raise
    finally:
        db.close()

def test_connections():
    """Probar conexiones a las bases de datos"""
    try:
        with engine_servidor.connect():
            logger.info("Conexión a base de datos servidor exitosa")
    except Exception as e:
        logger.error(f"Error conectando a base de datos servidor: {str(e)}")
        raise
    
    try:
        with engine_cliente.connect():
            logger.info("Conexión a base de datos cliente exitosa")
    except Exception as e:
        logger.error(f"Error conectando a base de datos cliente: {str(e)}")
        raise