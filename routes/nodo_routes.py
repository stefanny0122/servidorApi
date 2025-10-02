from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any
from services.autenticacion import ServicioAutenticacion
from services.gestor_nodos import GestorNodosImpl
from utils.logger import get_logger

router = APIRouter(prefix="/nodos", tags=["gestion_nodos"])
logger = get_logger("NodoRoutes")
security = HTTPBearer()

class NodoRegistroRequest(BaseModel):
    ip: str
    descripcion: str
    capacidad_total: int

class NodoEstadoUpdateRequest(BaseModel):
    estado: str  # activo, inactivo, mantenimiento
    capacidad_usada: int = 0

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

@router.post("/registrar", response_model=Dict[str, Any])
async def registrar_nodo(
    nodo_data: NodoRegistroRequest,
    token_data: dict = Depends(verificar_token_dependencia)
):
    """Registra un nuevo nodo worker en el sistema"""
    try:
        gestor = GestorNodosImpl()
        exito = gestor.registrar_nodo(
            ip=nodo_data.ip,
            descripcion=nodo_data.descripcion,
            capacidad_total=nodo_data.capacidad_total
        )
        
        if exito:
            return {"message": "Nodo registrado exitosamente", "ip": nodo_data.ip}
        else:
            raise HTTPException(status_code=400, detail="Error registrando nodo")
            
    except Exception as e:
        logger.error(f"Error registrando nodo: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/estado", response_model=List[Dict[str, Any]])
async def obtener_estado_nodos(token_data: dict = Depends(verificar_token_dependencia)):
    """Obtiene el estado de todos los nodos registrados"""
    try:
        gestor = GestorNodosImpl()
        nodos = gestor.obtener_estado_nodos()
        return nodos
    except Exception as e:
        logger.error(f"Error obteniendo estado de nodos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/disponible", response_model=Dict[str, Any])
async def obtener_nodo_disponible(token_data: dict = Depends(verificar_token_dependencia)):
    """Obtiene un nodo disponible para procesamiento"""
    try:
        gestor = GestorNodosImpl()
        nodo = gestor.obtener_nodo_disponible()
        
        if nodo:
            return nodo
        else:
            raise HTTPException(status_code=404, detail="No hay nodos disponibles")
    except Exception as e:
        logger.error(f"Error obteniendo nodo disponible: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.put("/{id_nodo}/estado")
async def actualizar_estado_nodo(
    id_nodo: int,
    estado_data: NodoEstadoUpdateRequest,
    token_data: dict = Depends(verificar_token_dependencia)
):
    """Actualiza el estado de un nodo especifico"""
    try:
        gestor = GestorNodosImpl()
        exito = gestor.actualizar_estado_nodo(
            id_nodo=id_nodo,
            estado=estado_data.estado,
            capacidad_usada=estado_data.capacidad_usada
        )
        
        if exito:
            return {"message": "Estado actualizado exitosamente"}
        else:
            raise HTTPException(status_code=404, detail="Nodo no encontrado")
            
    except Exception as e:
        logger.error(f"Error actualizando estado del nodo: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")