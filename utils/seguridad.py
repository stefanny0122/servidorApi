import hashlib
import hmac
import secrets
import string
from typing import Optional, Tuple
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi import HTTPException, status
from config import config
from utils.logger import get_logger

logger = get_logger("SeguridadUtils")

# Contexto para hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SeguridadUtils:
    
    # === HASHING Y VERIFICACIÓN DE CONTRASEÑAS ===
    @staticmethod
    def verificar_password(plain_password: str, hashed_password: str) -> bool:
        """Verifica si la contraseña plana coincide con el hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Genera hash seguro de contraseña usando bcrypt"""
        return pwd_context.hash(password)
    
    # === JWT TOKENS - VERSIÓN CORREGIDA ===
    @staticmethod
    def crear_token_acceso(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crea un token JWT de acceso - CORREGIDO"""
        try:
            to_encode = data.copy()
            
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            else:
                expire = datetime.utcnow() + timedelta(
                    minutes=config.jwt.access_token_expire_minutes
                )
            
            to_encode.update({
                "exp": expire,
                "iat": datetime.utcnow(),
                "iss": "sistema-procesamiento-imagenes"
            })
            
            logger.info(f"Creando token con expiración: {expire}")
            
            encoded_jwt = jwt.encode(
                to_encode, 
                config.jwt.secret_key, 
                algorithm=config.jwt.algorithm
            )
            
            logger.info(f"Token JWT creado para: {data.get('sub', 'Unknown')}")
            return encoded_jwt
            
        except Exception as e:
            logger.error(f"Error creando token JWT: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error generando token de acceso"
            )
    
    @staticmethod
    def verificar_token_acceso(token: str) -> Optional[dict]:
        """Verifica y decodifica un token JWT - CORREGIDO"""
        try:
            logger.info(f"Verificando token: {token[:50]}...")
            
            # Usar verify_exp=True para que jwt.decode maneje la expiración automáticamente
            payload = jwt.decode(
                token, 
                config.jwt.secret_key, 
                algorithms=[config.jwt.algorithm],
                options={"verify_exp": True}
            )
            
            logger.info(f"Token verificado exitosamente para: {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token JWT expirado")
            return None
        except JWTError as e:
            logger.warning(f"Token JWT inválido: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verificando token JWT: {e}")
            return None
    
    @staticmethod
    def crear_tokens_autenticacion(email: str, user_id: int, tipo: str) -> dict:
        """Crea tokens de acceso y refresh - CORREGIDO"""
        # Aumentar tiempo de expiración para testing
        access_token_expires = timedelta(minutes=config.jwt.access_token_expire_minutes)
        refresh_token_expires = timedelta(days=7)
        
        logger.info(f"Creando tokens para {email}, expiración: {access_token_expires}")
        
        access_token = SeguridadUtils.crear_token_acceso(
            data={"sub": email, "tipo": tipo, "id": user_id},
            expires_delta=access_token_expires
        )
        
        refresh_token = SeguridadUtils.crear_token_acceso(
            data={"sub": email, "tipo": "refresh", "id": user_id},
            expires_delta=refresh_token_expires
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": access_token_expires.total_seconds()
        }
    
    # === VALIDACIONES DE SEGURIDAD ===
    @staticmethod
    def validar_fortaleza_password(password: str) -> Tuple[bool, str]:
        """Valida la fortaleza de una contraseña"""
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres"
        
        if not any(c.islower() for c in password):
            return False, "La contraseña debe contener al menos una minúscula"
        
        if not any(c.isupper() for c in password):
            return False, "La contraseña debe contener al menos una mayúscula"
        
        if not any(c.isdigit() for c in password):
            return False, "La contraseña debe contener al menos un número"
        
        if not any(c in "!@#$%^&*" for c in password):
            return False, "La contraseña debe contener al menos un carácter especial (!@#$%^&*)"
        
        return True, "Contraseña segura"
    
    @staticmethod
    def validar_formato_email(email: str) -> bool:
        """Valida el formato básico de un email"""
        import re
        if not email or '@' not in email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None