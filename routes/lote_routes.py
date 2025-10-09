from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import json
import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from services.autenticacion import ServicioAutenticacion
from services.procesador_lotes import ProcesadorLotesImpl
from services import ClienteNodoWorker, BalanceadorCargaNodos
from config import config
from utils.logger import get_logger

router = APIRouter(prefix="/lotes", tags=["procesamiento_lotes"])
logger = get_logger("LoteRoutes")
security = HTTPBearer()

MAX_FILE_SIZE = 50 * 1024 * 1024   
MAX_FILES_PER_BATCH = 100   
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp', '.gif'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/tiff', 
    'image/bmp', 'image/webp', 'image/gif'
}
 
_procesador_lotes: Optional[ProcesadorLotesImpl] = None

def obtener_procesador_lotes() -> ProcesadorLotesImpl:
    """Retorna instancia singleton del procesador de lotes"""
    global _procesador_lotes
    if _procesador_lotes is None:
        _procesador_lotes = ProcesadorLotesImpl()
    return _procesador_lotes

async def verificar_token_dependencia(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Dependencia para verificar token de autenticación"""
    try:
        token = credentials.credentials
        servicio = ServicioAutenticacion()
        token_data = servicio.verificar_token(token)
        return token_data
    except ValueError as e:
        logger.warning(f"Token inválido: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación inválido",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Error verificando token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error de autenticación",
            headers={"WWW-Authenticate": "Bearer"}
        )

def validar_archivo(file: UploadFile) -> tuple[bool, Optional[str]]:
    """
    Valida un archivo subido
    Returns: (es_valido, mensaje_error)
    """
 
    if not file.filename:
        return False, "Archivo sin nombre"
     
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return False, f"Extensión no permitida: {extension}. Permitidas: {', '.join(ALLOWED_EXTENSIONS)}"
     
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"Tipo MIME no permitido: {file.content_type}"
    
    return True, None

def generar_nombre_unico(nombre_original: str) -> str:
    """Genera un nombre de archivo único para evitar colisiones"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_id = uuid.uuid4().hex[:8]
    extension = Path(nombre_original).suffix
    nombre_base = Path(nombre_original).stem
     
    nombre_base = "".join(c for c in nombre_base if c.isalnum() or c in ('-', '_'))
    
    return f"{timestamp}_{random_id}_{nombre_base}{extension}"

async def guardar_archivo_temporal(
    file: UploadFile, 
    directorio: str,
    id_lote: str
) -> tuple[str, int]:
    """
    Guarda un archivo temporal y retorna (ruta, tamaño_bytes)
    """ 
    directorio_lote = os.path.join(directorio, f"lote_{id_lote}")
    os.makedirs(directorio_lote, exist_ok=True)
     
    nombre_unico = generar_nombre_unico(file.filename)
    ruta_archivo = os.path.join(directorio_lote, nombre_unico)
     
    tamanio_total = 0
    chunk_size = 1024 * 1024  
    
    try:
        with open(ruta_archivo, "wb") as buffer:
            while chunk := await file.read(chunk_size):
                tamanio_total += len(chunk)
                 
                if tamanio_total > MAX_FILE_SIZE:
 
                    buffer.close()
                    os.remove(ruta_archivo)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE / (1024*1024):.0f}MB"
                    )
                
                buffer.write(chunk)
        
        logger.info(f"Archivo guardado: {nombre_unico} ({tamanio_total / 1024:.2f}KB)")
        return ruta_archivo, tamanio_total
        
    except HTTPException:
        raise
    except Exception as e:
 
        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo)
        logger.error(f"Error guardando archivo {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando archivo: {file.filename}"
        )

def validar_transformaciones(transformaciones_str: str) -> List[dict]:
    """Valida y parsea la lista de transformaciones"""
    try:
        transformaciones = json.loads(transformaciones_str)
        
        if not isinstance(transformaciones, list):
            raise ValueError("Las transformaciones deben ser una lista")
        
        if len(transformaciones) == 0:
            raise ValueError("Debe especificar al menos una transformación")
        
        if len(transformaciones) > 20:
            raise ValueError("Máximo 20 transformaciones por lote")
         
        for i, trans in enumerate(transformaciones):
            if not isinstance(trans, dict):
                raise ValueError(f"Transformación {i} debe ser un objeto")
            
            if "tipo" not in trans:
                raise ValueError(f"Transformación {i} debe tener campo 'tipo'")
            
            if not isinstance(trans.get("parametros", {}), dict):
                raise ValueError(f"Transformación {i}: 'parametros' debe ser un objeto")
        
        return transformaciones
        
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido en transformaciones: {e}")

@router.post("/procesar", status_code=status.HTTP_202_ACCEPTED)
async def procesar_lote(
    files: List[UploadFile] = File(..., description="Imágenes a procesar"),
    transformaciones: str = Form(..., description="Lista de transformaciones en formato JSON"),
    token_data: dict = Depends(verificar_token_dependencia),
    procesador: ProcesadorLotesImpl = Depends(obtener_procesador_lotes)
):
    """
    Endpoint para procesar un lote de imágenes con transformaciones.
    
    Retorna inmediatamente con un ID de lote que puede usarse para consultar el estado.
    """
    id_lote = uuid.uuid4().hex[:16]
    usuario_id = token_data.get('id')
    
    logger.info(
        f"[Lote {id_lote}] Iniciando procesamiento para usuario {usuario_id} - "
        f"{len(files)} archivos"
    )
    
    try: 
        if len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe proporcionar al menos un archivo"
            )
        
        if len(files) > MAX_FILES_PER_BATCH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Máximo {MAX_FILES_PER_BATCH} archivos por lote"
            )
         
        try:
            transformaciones_list = validar_transformaciones(transformaciones)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
 
        os.makedirs(config.upload_dir, exist_ok=True)
         
        imagenes_data = []
        archivos_guardados = []
        tamanio_total = 0
        
        for i, file in enumerate(files):
            try:
 
                es_valido, error = validar_archivo(file)
                if not es_valido:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Archivo '{file.filename}': {error}"
                    )
                 
                ruta_temporal, tamanio = await guardar_archivo_temporal(
                    file, config.upload_dir, id_lote
                )
                archivos_guardados.append(ruta_temporal)
                tamanio_total += tamanio
 
                imagenes_data.append({
                    'nombre_original': file.filename,
                    'formato_original': Path(file.filename).suffix.lower().lstrip('.'),
                    'ruta_temporal': ruta_temporal,
                    'transformaciones': transformaciones_list,
                    'tamanio_bytes': tamanio,
                    'indice': i
                })
                
            except HTTPException:
 
                for ruta in archivos_guardados:
                    try:
                        if os.path.exists(ruta):
                            os.remove(ruta)
                    except Exception as e:
                        logger.error(f"Error limpiando archivo {ruta}: {e}")
                raise
        
        logger.info(
            f"[Lote {id_lote}] {len(imagenes_data)} archivos guardados "
            f"({tamanio_total / (1024*1024):.2f}MB total)"
        )
        
 
        try:
            resultado = procesador.crear_solicitud_procesamiento(
                id_usuario=usuario_id, 
                imagenes=imagenes_data,
                
            )
            
            logger.info(f"[Lote {id_lote}] Solicitud de procesamiento creada exitosamente")
            
            return {
                "id_lote": id_lote,
                "estado": "en_proceso",
                "total_imagenes": len(imagenes_data),
                "transformaciones": len(transformaciones_list),
                "tamanio_total_mb": round(tamanio_total / (1024*1024), 2),
                "mensaje": "Lote aceptado para procesamiento",
                "timestamp": datetime.now().isoformat(),
                **resultado
            }
            
        except Exception as e: 
            for ruta in archivos_guardados:
                try:
                    if os.path.exists(ruta):
                        os.remove(ruta)
                except Exception as cleanup_error:
                    logger.error(f"Error limpiando archivo {ruta}: {cleanup_error}")
            raise
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Lote {id_lote}] Error procesando lote: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar el lote"
        )

@router.get("/estado/{id_lote}")
async def obtener_estado_lote(
    id_lote: str,
    token_data: dict = Depends(verificar_token_dependencia),
    procesador: ProcesadorLotesImpl = Depends(obtener_procesador_lotes)
):
    """Consulta el estado de un lote de procesamiento"""
    try:
        usuario_id = token_data.get('id')
        
        estado = procesador.obtener_estado_lote(id_lote, usuario_id)
        
        if not estado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lote {id_lote} no encontrado o no pertenece al usuario"
            )
        
        return estado
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo estado del lote {id_lote}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar el estado del lote"
        )

@router.get("/historial")
async def obtener_historial(
    limite: int = 10,
    offset: int = 0,
    token_data: dict = Depends(verificar_token_dependencia),
    procesador: ProcesadorLotesImpl = Depends(obtener_procesador_lotes)
):
    """Obtiene el historial de lotes procesados por el usuario"""
    try:
        usuario_id = token_data.get('id')
         
        if limite < 1 or limite > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El límite debe estar entre 1 y 100"
            )
        
        historial = procesador.obtener_historial_usuario(
            usuario_id=usuario_id,
            limite=limite,
            offset=offset
        )
        
        return {
            "historial": historial,
            "limite": limite,
            "offset": offset,
            "total": len(historial)
        }
        
    except HTTPException:
        raise