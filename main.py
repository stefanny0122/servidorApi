from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from config import config
from database import test_connections, init_db
from routes import auth_routes, lote_routes, nodo_routes, imagen_individual_routes
from utils.logger import get_logger

logger = get_logger("MainApp")

app = FastAPI(
    title="Sistema Distribuido Procesamiento de Imágenes",
    description="Servidor de aplicaciones para procesamiento paralelo de imágenes",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos
app.mount("/uploads", StaticFiles(directory=config.upload_dir), name="uploads")
app.mount("/results", StaticFiles(directory=config.results_dir), name="results")

# Routers
app.include_router(auth_routes.router)
app.include_router(lote_routes.router)
app.include_router(nodo_routes.router)
app.include_router(imagen_individual_routes.router)   

@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar la aplicación"""
    logger.info("Iniciando servidor de aplicaciones...")
    try:
        init_db()
        test_connections()
        logger.info("✓ Base de datos inicializada y conexiones verificadas")
    except Exception as e:
        logger.error(f"✗ Error inicializando base de datos: {e}")
        logger.info("Continuando sin base de datos...")

@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar la aplicación"""
    logger.info("Cerrando servidor de aplicaciones...")
    
    # Cerrar procesadores
    try:
        from routes.lote_routes import _procesador_lotes
        from routes.imagen_individual_routes import _procesador
        
        if _procesador_lotes:
            _procesador_lotes.shutdown()
        
        if _procesador:
            _procesador.shutdown()
        
        logger.info("✓ Procesadores cerrados correctamente")
    except Exception as e:
        logger.error(f"Error cerrando procesadores: {e}")

@app.get("/")
async def root():
    return {
        "message": "Servidor de aplicaciones funcionando correctamente",
        "version": "2.0.0",
        "endpoints": {
            "auth": "/auth",
            "lotes": "/lotes",
            "imagenes_individuales": "/lote-individual",
            "nodos": "/nodos"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "servidor_aplicaciones",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info"
    )