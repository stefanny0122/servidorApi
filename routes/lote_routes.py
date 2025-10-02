from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
import json
import os
from services.autenticacion import ServicioAutenticacion
from services.procesador_lotes import ProcesadorLotesImpl
from config import config
from utils.logger import get_logger

router = APIRouter(prefix="/lotes", tags=["procesamiento_lotes"])
logger = get_logger("LoteRoutes")
security = HTTPBearer()

# Dependencia local para evitar importacion circular
async def verificar_token_dependencia(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependencia local para verificar token"""
    try:
        token = credentials.credentials
        servicio = ServicioAutenticacion()
        token_data = servicio.verificar_token(token)
        return token_data
    except Exception as e:
        logger.error(f"Error verificando token: {e}")
        raise HTTPException(status_code=401, detail="Error de autenticacion")

@router.post("/procesar")
async def procesar_lote(
    files: List[UploadFile] = File(...),
    transformaciones: str = Form(...),
    token_data: dict = Depends(verificar_token_dependencia)
):
    """Endpoint para procesar un lote de imagenes"""
    try:
        # Parsear transformaciones
        transformaciones_list = json.loads(transformaciones)
        
        # Guardar archivos temporalmente
        imagenes_data = []
        for file in files:
            # Validar tipo de archivo
            if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
                raise HTTPException(status_code=400, detail=f"Formato no soportado: {file.filename}")
            
            # Guardar archivo temporal
            file_path = os.path.join(config.upload_dir, f"temp_{file.filename}")
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            imagenes_data.append({
                'nombre_original': file.filename,
                'formato_original': file.filename.split('.')[-1].lower(),
                'ruta_temporal': file_path,
                'transformaciones': transformaciones_list
            })
        
        # Procesar lote
        procesador = ProcesadorLotesImpl()
        resultado = procesador.crear_solicitud_procesamiento(
            token_data['id'],
            imagenes_data
        )
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error procesando lote: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")