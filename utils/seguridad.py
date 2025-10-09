import hashlib
import hmac
import secrets
import string
from typing import Optional, Tuple
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from config import config
from utils.logger import get_logger

logger = get_logger("SeguridadUtils")

class SeguridadUtils:
     
    @staticmethod
    def verificar_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verifica si la contraseña plana coincide con el hash
        Usa PBKDF2-HMAC-SHA256 (100,000 iteraciones - Estándar OWASP)
        """
        try:
 
            combined = bytes.fromhex(hashed_password) 
            salt = combined[:32]
            stored_hash = combined[32:]
             
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                plain_password.encode('utf-8'),
                salt,
                100000   
            )
            
           
            return hmac.compare_digest(pwd_hash, stored_hash)
            
        except ValueError as e:
 
            logger.warning(f"Hash en formato incorrecto: {e}")
            return False
        except Exception as e:
            logger.error(f"Error verificando contraseña: {e}")
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Genera hash seguro de contraseña usando PBKDF2-HMAC-SHA256
        - 100,000 iteraciones (OWASP 2023)
        - Salt único aleatorio de 32 bytes
        - Resultado: hex(salt + hash)
        """
        try:
 
            salt = secrets.token_bytes(32)
             
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000
            )
             
            combined = salt + pwd_hash
            return combined.hex()
            
        except Exception as e:
            logger.error(f"Error generando hash de contraseña: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error procesando la contraseña"
            )
     
    @staticmethod
    def crear_token_acceso(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crea un token JWT de acceso"""
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
        """Verifica y decodifica un token JWT"""
        try:
            logger.info(f"Verificando token: {token[:50]}...")
            
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
        """Crea tokens de acceso y refresh"""
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
            "expires_in": int(access_token_expires.total_seconds())
        }
     
    @staticmethod
    def validar_fortaleza_password(password: str, strict: bool = False) -> Tuple[bool, str]:
        """
        Valida la fortaleza de una contraseña
        strict=False: Solo requiere 6 caracteres (desarrollo/testing)
        strict=True: Requiere mayúsculas, minúsculas, números y especiales (producción)
        """
        if not password:
            return False, "La contraseña es requerida"
            
        if len(password) < 6:
            return False, "La contraseña debe tener al menos 6 caracteres"
        
        if not strict:
 
            logger.debug("Validación de password en modo permisivo (solo 6+ caracteres)")
            return True, "Contraseña válida"
        
 
        errores = []
        
        if not any(c.islower() for c in password):
            errores.append("una minúscula")
        
        if not any(c.isupper() for c in password):
            errores.append("una mayúscula")
        
        if not any(c.isdigit() for c in password):
            errores.append("un número")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errores.append("un carácter especial")
        
        if errores:
            return False, f"La contraseña debe contener al menos: {', '.join(errores)}"
        
        return True, "Contraseña segura"
    
    @staticmethod
    def validar_formato_email(email: str) -> bool:
        """Valida el formato básico de un email"""
        import re
        if not email or '@' not in email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def generar_token_seguro(length: int = 32) -> str:
        """Genera un token seguro aleatorio para reset de password, etc."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generar_codigo_verificacion(length: int = 6) -> str:
        """Genera un código numérico de verificación"""
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    @staticmethod
    def hash_simple(texto: str) -> str:
        """Hash simple usando SHA256 (para tokens, no para passwords)"""
        return hashlib.sha256(texto.encode('utf-8')).hexdigest()