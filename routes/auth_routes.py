from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
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
    
    @validator('password')
    def validate_password(cls, v):
        if not v or len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v

class RegistroRequest(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    tipo: str = "servidor"
    
    @validator('nombre')
    def validate_nombre(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('El nombre es requerido')
        if len(v.strip()) < 2:
            raise ValueError('El nombre debe tener al menos 2 caracteres')
        return v.strip()
    
    @validator('password')
    def validate_password(cls, v):
        if not v or len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v

class CambioPasswordRequest(BaseModel):
    old_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if not v or len(v) < 6:
            raise ValueError('La nueva contraseña debe tener al menos 6 caracteres')
        return v

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    tipo: str = "servidor"

class NuevoPasswordRequest(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if not v or len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v

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
    except ValueError as ve:
        logger.warning(f"Error de validacion en login: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
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
        logger.info(f"Intento de registro para: {registro_data.email}")
        
        servicio = ServicioAutenticacion()
        
        resultado = servicio.registrar_usuario(
            registro_data.nombre,
            registro_data.email,
            registro_data.password,
            registro_data.tipo
        )
        
        if not resultado.get("success", False):
            logger.warning(f"Registro fallido para {registro_data.email}: {resultado.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=resultado.get("error", "Error en el registro")
            )
        
        # Enviar email de bienvenida en segundo plano
        background_tasks.add_task(
            enviar_email_bienvenida,
            registro_data.email,
            registro_data.nombre
        )
        
        logger.info(f"Usuario registrado exitosamente: {registro_data.email}")
        
        return {
            "success": True,
            "message": "Usuario registrado exitosamente",
            "email": registro_data.email
        }
        
    except HTTPException:
        raise
    except ValueError as ve:
        logger.warning(f"Error de validacion en registro: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
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
        
        return {
            "success": True,
            "message": "Logout exitoso"
        }
        
    except Exception as e:
        logger.error(f"Error en logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante el logout"
        )

@router.post("/cambiar-password", response_model=Dict[str, Any])
async def cambiar_password(
    cambio_data: CambioPasswordRequest,
    usuario = Depends(obtener_usuario_actual)
):
    """Endpoint para cambiar contraseña del usuario actual"""
    try:
        servicio = ServicioAutenticacion()
        
        # Verificar contraseña actual
        usuario_auth = servicio.autenticar_usuario(
            usuario.email,
            cambio_data.old_password,
            getattr(usuario, 'tipo', 'servidor')
        )
        
        if not usuario_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Contraseña actual incorrecta"
            )
        
        # Cambiar contraseña
        resultado = servicio.cambiar_password(
            usuario.id_usuario,
            cambio_data.new_password,
            getattr(usuario, 'tipo', 'servidor')
        )
        
        if not resultado.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=resultado.get("error", "Error al cambiar contraseña")
            )
        
        logger.info(f"Contraseña cambiada exitosamente para: {usuario.email}")
        
        return {
            "success": True,
            "message": "Contraseña cambiada exitosamente"
        }
        
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error cambiando contraseña: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/reset-password", response_model=Dict[str, Any])
async def solicitar_reset_password(
    reset_data: ResetPasswordRequest,
    background_tasks: BackgroundTasks
):
    """Endpoint para solicitar reset de contraseña"""
    try:
        servicio = ServicioAutenticacion()
        
        # Generar token de reset
        token = servicio.generar_token_reset_password(
            reset_data.email,
            reset_data.tipo
        )
        
        if not token:
            # Por seguridad, no revelamos si el email existe o no
            logger.warning(f"Intento de reset para email no existente: {reset_data.email}")
            return {
                "success": True,
                "message": "Si el email existe, recibirás instrucciones para resetear tu contraseña"
            }
        
        # Enviar email con token
        background_tasks.add_task(
            enviar_email_reset_password,
            reset_data.email,
            token
        )
        
        logger.info(f"Token de reset generado para: {reset_data.email}")
        
        return {
            "success": True,
            "message": "Si el email existe, recibirás instrucciones para resetear tu contraseña"
        }
        
    except Exception as e:
        logger.error(f"Error en solicitud de reset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/nuevo-password", response_model=Dict[str, Any])
async def establecer_nuevo_password(nuevo_password_data: NuevoPasswordRequest):
    """Endpoint para establecer nueva contraseña con token de reset"""
    try:
        servicio = ServicioAutenticacion()
        
        resultado = servicio.resetear_password(
            nuevo_password_data.token,
            nuevo_password_data.new_password
        )
        
        if not resultado.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=resultado.get("error", "Token inválido o expirado")
            )
        
        logger.info("Contraseña reseteada exitosamente")
        
        return {
            "success": True,
            "message": "Contraseña actualizada exitosamente"
        }
        
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error estableciendo nuevo password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/verificar-email/{token}", response_model=Dict[str, Any])
async def verificar_email(token: str):
    """Endpoint para verificar email con token"""
    try:
        servicio = ServicioAutenticacion()
        
        resultado = servicio.verificar_email_token(token)
        
        if not resultado.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=resultado.get("error", "Token inválido o expirado")
            )
        
        logger.info(f"Email verificado exitosamente")
        
        return {
            "success": True,
            "message": "Email verificado exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verificando email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# Funciones auxiliares para emails
async def enviar_email_bienvenida(email: str, nombre: str):
    """Funcion para enviar email de bienvenida"""
    try:
        logger.info(f"Enviando email de bienvenida a {nombre} <{email}>")
        # Aquí implementarías el envío real del email
        # Por ejemplo usando SendGrid, AWS SES, etc.
    except Exception as e:
        logger.error(f"Error enviando email de bienvenida: {e}")

async def enviar_email_reset_password(email: str, token: str):
    """Funcion para enviar email de reset de contraseña"""
    try:
        logger.info(f"Enviando email de reset de password a {email}")
        # Aquí implementarías el envío real del email con el link de reset
        # reset_link = f"https://tu-app.com/reset-password?token={token}"
    except Exception as e:
        logger.error(f"Error enviando email de reset: {e}")