import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class JWTConfig:
    secret_key: str = os.getenv("JWT_SECRET_KEY", "clave-super-segura-minimo-32-caracteres-aqui-123456789")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120  # 2 horas para testing

@dataclass
class PyroConfig:
    ns_host: str = "localhost"
    ns_port: int = 9090

@dataclass
class SecurityConfig:
    allowed_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    rate_limit_requests: int = 100
    rate_limit_window: int = 900

@dataclass
class AppConfig:
    # Configuración servidor
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = True
    
    # Configuración base de datos servidor (Aiven)
    db_servidor: DatabaseConfig = field(default_factory=lambda: DatabaseConfig(
        host=os.getenv("DB_SERVIDOR_HOST", "localhost"),
        port=int(os.getenv("DB_SERVIDOR_PORT", "26414")),
        user=os.getenv("DB_SERVIDOR_USER", "avnadmin"),
        password=os.getenv("DB_SERVIDOR_PASSWORD", ""),
        database=os.getenv("DB_SERVIDOR_NAME", "Servidordb")
    ))
    
    # Configuración base de datos cliente (Aiven)
    db_cliente: DatabaseConfig = field(default_factory=lambda: DatabaseConfig(
        host=os.getenv("DB_CLIENTE_HOST", "localhost"),
        port=int(os.getenv("DB_CLIENTE_PORT", "21110")),
        user=os.getenv("DB_CLIENTE_USER", "avnadmin"),
        password=os.getenv("DB_CLIENTE_PASSWORD", ""),
        database=os.getenv("DB_CLIENTE_NAME", "ClienteDB")
    ))
    
    # Configuraciones adicionales
    jwt: JWTConfig = field(default_factory=JWTConfig)
    pyro: PyroConfig = field(default_factory=PyroConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Directorios
    upload_dir: str = "uploads"
    results_dir: str = "results"
    
    def get_db_url(self, db_type: str = "servidor") -> str:
        """Genera la URL de conexión para la base de datos"""
        if db_type == "servidor":
            db_config = self.db_servidor
        else:
            db_config = self.db_cliente
            
        return f"mysql+pymysql://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.database}"
    
    def __post_init__(self):
        # Crear directorios necesarios
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Verificar conexión a base de datos en modo debug
        if self.debug:
            self._verificar_conexiones()

    def _verificar_conexiones(self):
        """Verifica las conexiones a las bases de datos"""
        try:
            from sqlalchemy import create_engine, text
            
            # Verificar conexión a base de datos servidor
            engine_servidor = create_engine(self.get_db_url("servidor"))
            with engine_servidor.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print("CONEXION: Base de datos Servidor - EXITOSA")
            
            # Verificar conexión a base de datos cliente
            engine_cliente = create_engine(self.get_db_url("cliente"))
            with engine_cliente.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print("CONEXION: Base de datos Cliente - EXITOSA")
                
        except Exception as e:
            print(f"ERROR en conexión a base de datos: {e}")
            print("Verifica las credenciales en el archivo .env")

# Configuración global
config = AppConfig()