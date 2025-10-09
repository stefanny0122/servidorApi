from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_db_servidor, get_db_cliente
from models.usuario import UsuarioServidor
from models.cliente_models import UsuarioCliente
from utils.seguridad import SeguridadUtils
from utils.logger import get_logger

logger = get_logger("ServicioAutenticacion")
security = HTTPBearer()

class ServicioAutenticacion:
    
    @staticmethod
    def verificar_token(token: str) -> Dict[str, Any]:
        """Verifica y decodifica el token JWT"""
        payload = SeguridadUtils.verificar_token_acceso(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acceso invalido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    
    def obtener_usuario_por_id(self, user_id: int, tipo: str = "servidor"):
        """Obtiene usuario por ID"""
        try:
            if tipo == "servidor":
                with get_db_servidor() as db:
                    return db.query(UsuarioServidor).filter(UsuarioServidor.id_usuario == user_id).first()
            else:
                with get_db_cliente() as db:
                    return db.query(UsuarioCliente).filter(UsuarioCliente.id_usuario == user_id).first()
        except Exception as e:
            logger.error(f"Error obteniendo usuario por ID {user_id}: {e}")
            return None
    
    def obtener_usuario_por_email(self, email: str, tipo: str = "servidor"):
        """Obtiene usuario por email"""
        try:
            if tipo == "servidor":
                with get_db_servidor() as db:
                    return db.query(UsuarioServidor).filter(UsuarioServidor.email == email).first()
            else:
                with get_db_cliente() as db:
                    return db.query(UsuarioCliente).filter(UsuarioCliente.email == email).first()
        except Exception as e:
            logger.error(f"Error obteniendo usuario por email {email}: {e}")
            return None
    
    def autenticar_usuario(self, email: str, password: str, tipo: str = "servidor") -> Optional[Any]:
        """Autentica usuario en servidor o cliente - CORREGIDO"""
        try:
 
            if tipo == "servidor":
                with get_db_servidor() as db:
                    usuario = db.query(UsuarioServidor).filter(UsuarioServidor.email == email).first()
                    
                    if not usuario:
                        logger.warning(f"Intento de login con email no registrado: {email}")
                        return None
                    
                    
                    if not SeguridadUtils.verificar_password(password, usuario.contraseña):
                        logger.warning(f"Contraseña incorrecta para usuario: {email}")
                        return None
                     
                    return {
                        'id_usuario': usuario.id_usuario,
                        'nombre': usuario.nombre,
                        'email': usuario.email,
                        'tipo': tipo
                    }
            else:
                with get_db_cliente() as db:
                    usuario = db.query(UsuarioCliente).filter(UsuarioCliente.email == email).first()
                    
                    if not usuario:
                        logger.warning(f"Intento de login con email no registrado: {email}")
                        return None
                    
                    if not SeguridadUtils.verificar_password(password, usuario.contraseña):
                        logger.warning(f"Contraseña incorrecta para usuario: {email}")
                        return None
                    
                    return {
                        'id_usuario': usuario.id_usuario,
                        'nombre': usuario.nombre,
                        'email': usuario.email,
                        'tipo': tipo
                    }
            
        except Exception as e:
            logger.error(f"Error autenticando usuario {email}: {e}")
            return None
    
    def registrar_usuario(self, nombre: str, email: str, password: str, tipo: str = "servidor") -> Dict[str, Any]:
        """Registra nuevo usuario con validaciones de seguridad"""
        try: 
            if not SeguridadUtils.validar_formato_email(email):
                return {"success": False, "error": "Formato de email invalido"}
            
            es_segura, mensaje = SeguridadUtils.validar_fortaleza_password(password)
            if not es_segura:
                return {"success": False, "error": mensaje}
             
            usuario_existente = self.obtener_usuario_por_email(email, tipo)
            if usuario_existente:
                return {"success": False, "error": "El email ya esta registrado"}
             
            hashed_password = SeguridadUtils.get_password_hash(password)
             
            if tipo == "servidor":
                with get_db_servidor() as db:
                    nuevo_usuario = UsuarioServidor(
                        nombre=nombre,
                        email=email,
                        contraseña=hashed_password
                    )
                    db.add(nuevo_usuario)
                    db.commit()
                    user_id = nuevo_usuario.id_usuario
            else:
                with get_db_cliente() as db:
                    nuevo_usuario = UsuarioCliente(
                        nombre=nombre,
                        email=email,
                        contraseña=hashed_password
                    )
                    db.add(nuevo_usuario)
                    db.commit()
                    user_id = nuevo_usuario.id_usuario
            
            logger.info(f"Usuario registrado exitosamente: {email}")
            return {
                "success": True, 
                "user_id": user_id,
                "message": "Usuario registrado exitosamente"
            }
            
        except Exception as e:
            logger.error(f"Error registrando usuario {email}: {e}")
            return {"success": False, "error": "Error interno del servidor"}
    
    def cambiar_password(self, email: str, old_password: str, new_password: str, tipo: str = "servidor") -> bool:
        """Cambia la contraseña de un usuario"""
        try:
            usuario = self.autenticar_usuario(email, old_password, tipo)
            if not usuario:
                return False
            
            es_segura, mensaje = SeguridadUtils.validar_fortaleza_password(new_password)
            if not es_segura:
                return False
            
            new_hashed_password = SeguridadUtils.get_password_hash(new_password)
            
            if tipo == "servidor":
                with get_db_servidor() as db:
                    usuario_db = db.query(UsuarioServidor).filter(UsuarioServidor.email == email).first()
                    usuario_db.contraseña = new_hashed_password
                    db.commit()
            else:
                with get_db_cliente() as db:
                    usuario_db = db.query(UsuarioCliente).filter(UsuarioCliente.email == email).first()
                    usuario_db.contraseña = new_hashed_password
                    db.commit()
            
            logger.info(f"Contraseña cambiada exitosamente para: {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error cambiando contraseña para {email}: {e}")
            return False