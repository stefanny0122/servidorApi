from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import json
import os
import uuid
from pathlib import Path
from datetime import datetime

from services.autenticacion import ServicioAutenticacion
from services.procesador_imagen_individual import ProcesadorLoteIndividual  # CORREGIDO
from config import config
from utils.logger import get_logger

router = APIRouter(prefix="/lote-individual", tags=["procesamiento_lote_individual"])
logger = get_logger("LoteIndividualRoutes")
security = HTTPBearer()

# Constantes
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_FILES_PER_BATCH = 100
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp', '.gif'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/tiff',
    'image/bmp', 'image/webp', 'image/gif'
}

# Singleton del procesador
_procesador: Optional[ProcesadorLoteIndividual] = None

def obtener_procesador() -> ProcesadorLoteIndividual:
    """Retorna instancia singleton del procesador"""
    global _procesador
    if _procesador is None:
        _procesador = ProcesadorLoteIndividual(max_workers=10)
    return _procesador


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
    """Valida un archivo subido"""
    if not file.filename:
        return False, "Archivo sin nombre"
    
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return False, f"Extensión no permitida: {extension}"
    
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"Tipo MIME no permitido: {file.content_type}"
    
    return True, None


def generar_nombre_unico(nombre_original: str) -> str:
    """Genera un nombre de archivo único"""
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
    """Guarda archivo temporal y retorna (ruta, tamaño_bytes)"""
    directorio_lote = os.path.join(directorio, f"lote_{id_lote}")
    os.makedirs(directorio_lote, exist_ok=True)
    
    nombre_unico = generar_nombre_unico(file.filename)
    ruta_archivo = os.path.join(directorio_lote, nombre_unico)
    
    tamanio_total = 0
    chunk_size = 1024 * 1024  # 1MB
    
    try:
        with open(ruta_archivo, "wb") as buffer:
            while chunk := await file.read(chunk_size):
                tamanio_total += len(chunk)
                
                if tamanio_total > MAX_FILE_SIZE:
                    buffer.close()
                    os.remove(ruta_archivo)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Archivo {file.filename} demasiado grande. Máximo: {MAX_FILE_SIZE / (1024*1024):.0f}MB"
                    )
                
                buffer.write(chunk)
        
        logger.info(f"Archivo guardado: {nombre_unico} ({tamanio_total / 1024:.2f}KB)")
        return ruta_archivo, tamanio_total
        
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo)
        logger.error(f"Error guardando archivo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando archivo: {file.filename}"
        )


def validar_especificaciones(especificaciones_str: str, num_archivos: int) -> dict:
    """
    Valida y parsea las especificaciones de transformaciones por imagen
    
    Formato esperado:
    {
        "imagen1.jpg": [
            {"tipo": "resize", "parametros": {...}},
            {"tipo": "rotar", "parametros": {...}}
        ],
        "imagen2.jpg": [
            {"tipo": "filtro", "parametros": {...}}
        ]
    }
    """
    try:
        especificaciones = json.loads(especificaciones_str)
        
        if not isinstance(especificaciones, dict):
            raise ValueError("Las especificaciones deben ser un objeto JSON")
        
        if len(especificaciones) != num_archivos:
            raise ValueError(
                f"Se esperan especificaciones para {num_archivos} archivos, "
                f"pero se recibieron {len(especificaciones)}"
            )
        
        # Validar cada conjunto de transformaciones
        for nombre_archivo, transformaciones in especificaciones.items():
            if not isinstance(transformaciones, list):
                raise ValueError(f"Las transformaciones para '{nombre_archivo}' deben ser una lista")
            
            if len(transformaciones) == 0:
                raise ValueError(f"'{nombre_archivo}' debe tener al menos una transformación")
            
            if len(transformaciones) > 50:
                raise ValueError(f"'{nombre_archivo}' excede el máximo de 50 transformaciones")
            
            # Validar cada transformación
            for i, trans in enumerate(transformaciones):
                if not isinstance(trans, dict):
                    raise ValueError(
                        f"'{nombre_archivo}' - Transformación {i} debe ser un objeto"
                    )
                
                if "tipo" not in trans:
                    raise ValueError(
                        f"'{nombre_archivo}' - Transformación {i} debe tener campo 'tipo'"
                    )
                
                if not isinstance(trans.get("parametros", {}), dict):
                    raise ValueError(
                        f"'{nombre_archivo}' - Transformación {i}: 'parametros' debe ser un objeto"
                    )
        
        return especificaciones
        
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido en especificaciones: {e}")


@router.post("/procesar", status_code=status.HTTP_202_ACCEPTED)
async def procesar_lote_individual(
    files: List[UploadFile] = File(..., description="Imágenes a procesar"),
    especificaciones: str = Form(..., description="Especificaciones de transformaciones por imagen en formato JSON"),
    token_data: dict = Depends(verificar_token_dependencia),
    procesador: ProcesadorLoteIndividual = Depends(obtener_procesador)
):
    """
    Procesa un lote de imágenes donde cada una tiene sus propias transformaciones específicas.
    
    **Formato de especificaciones:**
    ```json
    {
        "foto1.jpg": [
            {"tipo": "resize", "parametros": {"ancho": 800, "alto": 600}},
            {"tipo": "rotar", "parametros": {"grados": 90}}
        ],
        "foto2.jpg": [
            {"tipo": "filtro", "parametros": {"tipo": "sepia"}},
            {"tipo": "ajustar_brillo", "parametros": {"factor": 1.2}}
        ],
        "foto3.jpg": [
            {"tipo": "escala_grises", "parametros": {}}
        ]
    }
    ```
    
    **Importante:** El nombre de cada imagen debe coincidir exactamente con el nombre del archivo subido.
    
    Retorna inmediatamente con un ID de lote.
    """
    id_lote = uuid.uuid4().hex[:16]
    usuario_id = token_data.get('id')
    
    logger.info(
        f"[Lote {id_lote}] Iniciando procesamiento individual para usuario {usuario_id} - "
        f"{len(files)} archivos"
    )
    
    archivos_guardados = []
    
    try:
        # Validar número de archivos
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
        
        # Validar especificaciones
        try:
            especificaciones_dict = validar_especificaciones(especificaciones, len(files))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        # Crear directorio de uploads
        os.makedirs(config.upload_dir, exist_ok=True)
        
        # Procesar cada archivo
        imagenes_data = []
        tamanio_total = 0
        
        for i, file in enumerate(files):
            try:
                # Validar archivo
                es_valido, error = validar_archivo(file)
                if not es_valido:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Archivo '{file.filename}': {error}"
                    )
                
                # Verificar que existan especificaciones para este archivo
                if file.filename not in especificaciones_dict:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"No se encontraron especificaciones para '{file.filename}'"
                    )
                
                # Guardar archivo
                ruta_temporal, tamanio = await guardar_archivo_temporal(
                    file, config.upload_dir, id_lote
                )
                archivos_guardados.append(ruta_temporal)
                tamanio_total += tamanio
                
                # Obtener transformaciones específicas para esta imagen
                transformaciones_imagen = especificaciones_dict[file.filename]
                
                # Preparar datos
                imagenes_data.append({
                    'nombre_original': file.filename,
                    'formato_original': Path(file.filename).suffix.lower().lstrip('.'),
                    'ruta_temporal': ruta_temporal,
                    'transformaciones': transformaciones_imagen,
                    'tamanio_bytes': tamanio,
                    'indice': i
                })
                
                logger.info(
                    f"[Lote {id_lote}] Archivo {i+1}/{len(files)}: {file.filename} - "
                    f"{len(transformaciones_imagen)} transformaciones específicas"
                )
                
            except HTTPException:
                # Limpiar archivos guardados si hay error
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
        
        # Enviar a procesamiento
        try:
            resultado = procesador.procesar_lote(
                id_lote=id_lote,
                id_usuario=usuario_id,
                imagenes=imagenes_data
            )
            
            logger.info(f"[Lote {id_lote}] Procesamiento iniciado exitosamente")
            
            return {
                "id_lote": id_lote,
                "estado": "procesando",
                "total_imagenes": len(imagenes_data),
                "tamanio_total_mb": round(tamanio_total / (1024*1024), 2),
                "mensaje": "Lote aceptado para procesamiento con especificaciones individuales",
                "timestamp": datetime.now().isoformat(),
                **resultado
            }
            
        except Exception as e:
            # Limpiar archivos si falla el procesamiento
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
    procesador: ProcesadorLoteIndividual = Depends(obtener_procesador)
):
    """Consulta el estado de un lote de procesamiento individual"""
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
    limite: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    token_data: dict = Depends(verificar_token_dependencia),
    procesador: ProcesadorLoteIndividual = Depends(obtener_procesador)
):
    """Obtiene el historial de lotes procesados por el usuario"""
    try:
        usuario_id = token_data.get('id')
        
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
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el historial"
        )


@router.get("/detalle/{id_lote}")
async def obtener_detalle_imagenes(
    id_lote: str,
    token_data: dict = Depends(verificar_token_dependencia),
    procesador: ProcesadorLoteIndividual = Depends(obtener_procesador)
):
    """Obtiene el detalle de cada imagen del lote con sus transformaciones específicas"""
    try:
        usuario_id = token_data.get('id')
        
        detalle = procesador.obtener_detalle_imagenes(id_lote, usuario_id)
        
        if not detalle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lote {id_lote} no encontrado"
            )
        
        return detalle
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo detalle del lote: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el detalle del lote"
        )