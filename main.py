from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from config import config
from database import test_connections, init_db  # Agregar init_db
from routes import auth_routes, lote_routes, nodo_routes
from utils.logger import get_logger

logger = get_logger("MainApp")

app = FastAPI(
    title="Sistema Distribuido Procesamiento de Imágenes",
    description="Servidor de aplicaciones para procesamiento paralelo de imágenes",
    version="1.0.0"
)

# CORS mejorado
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporalmente permitir todos para debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar directorios estáticos
app.mount("/uploads", StaticFiles(directory=config.upload_dir), name="uploads")
app.mount("/results", StaticFiles(directory=config.results_dir), name="results")

# Incluir rutas
app.include_router(auth_routes.router)
app.include_router(lote_routes.router)
app.include_router(nodo_routes.router)

@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar la aplicación"""
    logger.info("Iniciando servidor de aplicaciones...")
    try:
        # Inicializar tablas primero
        init_db()
        test_connections()
        logger.info("Base de datos inicializada y conexiones verificadas")
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        logger.info("Continuando sin base de datos...")

@app.get("/")
async def root():
    return {"message": "Servidor de aplicaciones funcionando correctamente"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "servidor_aplicaciones"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info"  # Agregar nivel de log
    )