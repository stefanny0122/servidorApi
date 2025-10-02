from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from services.autenticacion import ServicioAutenticacion
from utils.seguridad import SeguridadUtils
from utils.logger import get_logger

router = APIRouter(prefix="/auth", tags=["autenticacion"])
security = HTTPBearer()
logger = get_logger("AuthRoutes")

# Modelos Pydantic
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tipo: str = "servidor"

class RegistroRequest(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    tipo: str = "servidor"

class CambioPasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    tipo: str = "servidor"

class NuevoPasswordRequest(BaseModel):
    token: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    email: str
    tipo: str
    fecha_registro: Optional[str] = None

# Dependencia para verificar token
async def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Funcion para verificar el token"""
    try:
        token = credentials.credentials
        servicio = ServicioAutenticacion()
        token_data = servicio.verificar_token(token)
        return token_data
    except Exception as e:
        logger.error(f"Error verificando token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error de autenticacion",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Dependencia para obtener usuario actual
async def obtener_usuario_actual(token_data: Dict[str, Any] = Depends(verificar_token)):
    """Obtiene el usuario actual basado en el token"""
    try:
        servicio = ServicioAutenticacion()
        usuario = servicio.obtener_usuario_por_id(
            token_data.get("id"), 
            token_data.get("tipo", "servidor")
        )
        
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )
        
        return usuario
    except Exception as e:
        logger.error(f"Error obteniendo usuario actual: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error obteniendo informacion del usuario"
        )

@router.post("/login", response_model=Dict[str, Any])
async def login(login_data: LoginRequest):
    """Endpoint para login de usuarios"""
    try:
        logger.info(f"Intento de login para: {login_data.email}")
        
        servicio = ServicioAutenticacion()
        usuario = servicio.autenticar_usuario(
            login_data.email, 
            login_data.password, 
            login_data.tipo
        )
        
        if not usuario:
            logger.warning(f"Intento de login fallido para: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Crear tokens
        tokens = SeguridadUtils.crear_tokens_autenticacion(
            email=login_data.email,
            user_id=usuario['id_usuario'],
            tipo=login_data.tipo
        )
        
        logger.info(f"Login exitoso para usuario: {login_data.email}")
        
        return {
            **tokens,
            "usuario": {
                "id": usuario['id_usuario'],
                "nombre": usuario['nombre'],
                "email": usuario['email'],
                "tipo": login_data.tipo
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante el login"
        )

@router.post("/registro", response_model=Dict[str, Any])
async def registro(registro_data: RegistroRequest, background_tasks: BackgroundTasks):
    """Endpoint para registro de nuevos usuarios"""
    try:
        servicio = ServicioAutenticacion()
        
        resultado = servicio.registrar_usuario(
            registro_data.nombre,
            registro_data.email,
            registro_data.password,
            registro_data.tipo
        )
        
        if not resultado.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=resultado.get("error", "Error en el registro")
            )
        
        logger.info(f"Usuario registrado exitosamente: {registro_data.email}")
        
        return {
            "message": "Usuario registrado exitosamente",
            "email": registro_data.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en registro: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante el registro"
        )

@router.get("/me", response_model=UsuarioResponse)
async def obtener_usuario_actual_endpoint(usuario = Depends(obtener_usuario_actual)):
    """Obtiene informacion del usuario actual"""
    try:
        return UsuarioResponse(
            id=usuario.id_usuario,
            nombre=usuario.nombre,
            email=usuario.email,
            tipo=getattr(usuario, 'tipo', 'servidor'),
            fecha_registro=usuario.fecha_registro.isoformat() if hasattr(usuario, 'fecha_registro') and usuario.fecha_registro else None
        )
    except Exception as e:
        logger.error(f"Error obteniendo usuario actual: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo informacion del usuario"
        )

@router.post("/logout", response_model=Dict[str, Any])
async def logout(token_data: dict = Depends(verificar_token)):
    """Endpoint para logout"""
    try:
        logger.info(f"Logout exitoso para usuario: {token_data.get('sub')}")
        
        return {"message": "Logout exitoso"}
        
    except Exception as e:
        logger.error(f"Error en logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante el logout"
        )

# Funciones auxiliares para emails
async def enviar_email_bienvenida(email: str, nombre: str):
    """Funcion para enviar email de bienvenida"""
    try:
        logger.info(f"Email de bienvenida enviado a {nombre} <{email}>")
    except Exception as e:
        logger.error(f"Error enviando email de bienvenida: {e}")

async def enviar_email_reset_password(email: str, token: str):
    """Funcion para enviar email de reset de contraseña"""
    try:
        logger.info(f"Email de reset de password enviado a {email} con token: {token}")
    except Exception as e:
        logger.error(f"Error enviando email de reset: {e}")