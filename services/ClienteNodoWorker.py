"""
Cliente Pyro5 para comunicación con Nodos Workers
Este módulo se usa en el servidor FastAPI para comunicarse con nodos remotos
CON TRANSFERENCIA DE ARCHIVOS
"""

import Pyro5.api
import Pyro5.errors
from typing import Dict, Any, List, Optional
from utils.logger import get_logger
import time
import base64
import os

logger = get_logger("ClienteNodoWorker")


class ClienteNodoWorker:
    """
    Cliente para comunicarse con nodos workers remotos vía Pyro5.
    Usado por el servidor FastAPI para enviar trabajos.
    """
    
    def __init__(self, timeout: int = 300):
        """
        Args:
            timeout: Timeout en segundos para llamadas RPC (default: 5min)
        """
        self.timeout = timeout
        self._ns_cache = None
        self._last_ns_refresh = 0
        self.NS_CACHE_TTL = 60   
    
    def _obtener_nameserver(self) -> Pyro5.api.Proxy:
        """Obtiene proxy al NameServer con cache"""
        ahora = time.time()
        
        if self._ns_cache is None or (ahora - self._last_ns_refresh) > self.NS_CACHE_TTL:
            try:
                self._ns_cache = Pyro5.api.locate_ns()
                self._last_ns_refresh = ahora
                logger.debug("NameServer cache actualizado")
            except Pyro5.errors.NamingError as e:
                logger.error(f"Error conectando con NameServer: {e}")
                raise ConnectionError("No se puede conectar con NameServer")
        
        return self._ns_cache
    
    def listar_nodos_disponibles(self) -> List[str]:
        """
        Lista todos los nodos workers registrados en el NameServer.
        
        Returns:
            Lista de IDs de nodos (ej: ['worker01', 'worker02'])
        """
        try:
            ns = self._obtener_nameserver()
            registros = ns.list(prefix="nodo.")
            
            nodos = [nombre.replace("nodo.", "") for nombre in registros.keys()]
            logger.info(f"Nodos disponibles: {nodos}")
            return nodos
            
        except Exception as e:
            logger.error(f"Error listando nodos: {e}")
            return []
    
    def obtener_proxy_nodo(self, id_nodo: str) -> Optional[Pyro5.api.Proxy]:
        """
        Obtiene un proxy Pyro5 para comunicarse con un nodo específico.
        
        Args:
            id_nodo: ID del nodo (ej: 'worker01')
            
        Returns:
            Proxy al nodo o None si no está disponible
        """
        try:
            ns = self._obtener_nameserver()
            nombre_completo = f"nodo.{id_nodo}"
            
            uri = ns.lookup(nombre_completo)
            proxy = Pyro5.api.Proxy(uri)
            proxy._pyroTimeout = self.timeout
            
            logger.debug(f"Proxy creado para nodo {id_nodo}")
            return proxy
            
        except Pyro5.errors.NamingError:
            logger.warning(f"Nodo {id_nodo} no encontrado en NameServer")
            return None
        except Exception as e:
            logger.error(f"Error creando proxy para {id_nodo}: {e}")
            return None
    
    def ping_nodo(self, id_nodo: str) -> bool:
        """
        Verifica si un nodo está activo y responde.
        
        Args:
            id_nodo: ID del nodo
            
        Returns:
            True si el nodo responde, False en caso contrario
        """
        try:
            proxy = self.obtener_proxy_nodo(id_nodo)
            if not proxy:
                return False
            
            respuesta = proxy.ping()
            esta_activo = respuesta.get("activo", False)
            
            if esta_activo:
                logger.debug(f"Nodo {id_nodo} responde OK")
            else:
                logger.warning(f"Nodo {id_nodo} responde pero no está activo")
            
            return esta_activo
            
        except Exception as e:
            logger.warning(f"Nodo {id_nodo} no responde al ping: {e}")
            return False
    
    def obtener_estado_nodo(self, id_nodo: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado detallado de un nodo.
        
        Args:
            id_nodo: ID del nodo
            
        Returns:
            Dict con estado del nodo o None si no está disponible
        """
        try:
            proxy = self.obtener_proxy_nodo(id_nodo)
            if not proxy:
                return None
            
            estado = proxy.obtener_estado()
            logger.debug(f"Estado de {id_nodo}: {estado.get('estado')}")
            return estado
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de {id_nodo}: {e}")
            return None
    
    def verificar_disponibilidad(self, id_nodo: str) -> bool:
        """
        Verifica si un nodo puede aceptar más trabajos.
        
        Args:
            id_nodo: ID del nodo
            
        Returns:
            True si el nodo está disponible para trabajar
        """
        try:
            proxy = self.obtener_proxy_nodo(id_nodo)
            if not proxy:
                return False
            
            disponible = proxy.esta_disponible()
            logger.debug(f"Nodo {id_nodo} disponible: {disponible}")
            return disponible
            
        except Exception as e:
            logger.warning(f"Error verificando disponibilidad de {id_nodo}: {e}")
            return False
    
    def enviar_trabajo_con_archivos(
        self,
        id_nodo: str,
        id_trabajo: str,
        ruta_entrada: str,
        ruta_salida: str,
        transformaciones: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        ENVÍA TRABAJO CON TRANSFERENCIA DE ARCHIVOS
        Lee la imagen del servidor, la codifica en base64, la envía al nodo,
        y guarda el resultado devuelto.
        
        Args:
            id_nodo: ID del nodo worker
            id_trabajo: ID único del trabajo
            ruta_entrada: Ruta local del archivo de entrada
            ruta_salida: Ruta local donde guardar el resultado
            transformaciones: Lista de transformaciones a aplicar
            
        Returns:
            Dict con resultado del procesamiento
        """
        try:
            logger.info(
                f"Enviando trabajo {id_trabajo} a nodo {id_nodo} con transferencia de archivos - "
                f"{len(transformaciones)} transformaciones"
            )
            
            proxy = self.obtener_proxy_nodo(id_nodo)
            if not proxy:
                logger.error(f"No se pudo obtener proxy para nodo {id_nodo}")
                return {
                    "id_trabajo": id_trabajo,
                    "nodo": id_nodo,
                    "exito": False,
                    "error": "Nodo no disponible"
                }
             
            if not os.path.exists(ruta_entrada):
                return {
                    "id_trabajo": id_trabajo,
                    "exito": False,
                    "error": f"Archivo de entrada no existe: {ruta_entrada}"
                }
             
            with open(ruta_entrada, "rb") as f:
                imagen_codificada = base64.b64encode(f.read()).decode('utf-8')
             
            nombre_archivo = os.path.basename(ruta_entrada)
             
            resultado = proxy.procesar_con_archivo(
                id_trabajo=id_trabajo,
                nombre_archivo=nombre_archivo,
                imagen_codificada=imagen_codificada,
                transformaciones=transformaciones
            )
             
            if resultado.get("exito") and resultado.get("imagen_resultado"):
                try: 
                    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
                     
                    imagen_decodificada = base64.b64decode(resultado["imagen_resultado"])
                    with open(ruta_salida, "wb") as f:
                        f.write(imagen_decodificada)
                    
                    resultado["ruta_resultado"] = ruta_salida
                    tamanio = os.path.getsize(ruta_salida)
                    resultado["tamanio_resultado_kb"] = round(tamanio / 1024, 2)
                    
                    logger.info(
                        f"✓ Trabajo {id_trabajo} completado - "
                        f"Resultado guardado: {ruta_salida} ({tamanio/1024:.2f}KB)"
                    )
                    
                except Exception as e:
                    logger.error(f"Error guardando resultado: {e}")
                    resultado["exito"] = False
                    resultado["error"] = f"Error guardando resultado: {str(e)}"
            
            if resultado.get("exito"):
                logger.info(
                    f"✓ Trabajo {id_trabajo} completado en nodo {id_nodo} - "
                    f"Tiempo: {resultado.get('tiempo_procesamiento', 0):.2f}s"
                )
            else:
                logger.error(
                    f"✗ Trabajo {id_trabajo} falló en nodo {id_nodo}: "
                    f"{resultado.get('error', 'Error desconocido')}"
                )
            
            return resultado
            
        except Pyro5.errors.TimeoutError:
            logger.error(f"Timeout procesando trabajo {id_trabajo} en nodo {id_nodo}")
            return {
                "id_trabajo": id_trabajo,
                "nodo": id_nodo,
                "exito": False,
                "error": f"Timeout después de {self.timeout}s"
            }
        except Pyro5.errors.CommunicationError as e:
            logger.error(f"Error de comunicación con nodo {id_nodo}: {e}")
            return {
                "id_trabajo": id_trabajo,
                "nodo": id_nodo,
                "exito": False,
                "error": "Error de comunicación con el nodo"
            }
        except Exception as e:
            logger.error(
                f"Error enviando trabajo {id_trabajo} a nodo {id_nodo}: {e}",
                exc_info=True
            )
            return {
                "id_trabajo": id_trabajo,
                "nodo": id_nodo,
                "exito": False,
                "error": str(e)
            }
    
    def enviar_trabajo(
        self,
        id_nodo: str,
        id_trabajo: str,
        ruta_entrada: str,
        ruta_salida: str,
        transformaciones: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        MÉTODO ORIGINAL - ahora usa transferencia de archivos por defecto
        """
        return self.enviar_trabajo_con_archivos(
            id_nodo, id_trabajo, ruta_entrada, ruta_salida, transformaciones
        )


class BalanceadorCargaNodos:
    """
    Balanceador de carga para distribuir trabajos entre nodos workers.
    Implementa estrategia de menor carga.
    """
    
    def __init__(self):
        self.cliente = ClienteNodoWorker()
        
    def obtener_nodo_optimo(self) -> Optional[str]:
        """
        Selecciona el mejor nodo para procesar un trabajo.
        Usa estrategia de menor carga actual.
        
        Returns:
            ID del nodo óptimo o None si no hay nodos disponibles
        """
        try:
            nodos = self.cliente.listar_nodos_disponibles()
            
            if not nodos:
                logger.warning("No hay nodos registrados")
                return None
             
            estados = []
            for id_nodo in nodos:
                estado = self.cliente.obtener_estado_nodo(id_nodo)
                if estado and estado.get("estado") == "activo":
                    estados.append((id_nodo, estado))
            
            if not estados:
                logger.warning("No hay nodos activos")
                return None
             
            nodo_optimo = min(
                estados,
                key=lambda x: x[1].get("trabajos_activos", 999)
            )
            
            id_nodo = nodo_optimo[0]
            carga = nodo_optimo[1].get("trabajos_activos", 0)
            capacidad = nodo_optimo[1].get("capacidad_maxima", 0)
            
            logger.info(
                f"Nodo seleccionado: {id_nodo} "
                f"(carga: {carga}/{capacidad})"
            )
            
            return id_nodo
            
        except Exception as e:
            logger.error(f"Error seleccionando nodo óptimo: {e}")
            return None
    
    def obtener_estado_cluster(self) -> Dict[str, Any]:
        """
        Obtiene el estado agregado de todos los nodos.
        
        Returns:
            Dict con estadísticas del cluster
        """
        try:
            nodos = self.cliente.listar_nodos_disponibles()
            
            total_nodos = len(nodos)
            nodos_activos = 0
            trabajos_totales = 0
            capacidad_total = 0
            capacidad_usada = 0
            
            detalles_nodos = []
            
            for id_nodo in nodos:
                estado = self.cliente.obtener_estado_nodo(id_nodo)
                if estado:
                    detalles_nodos.append(estado)
                    
                    if estado.get("estado") == "activo":
                        nodos_activos += 1
                    
                    trabajos_totales += estado.get("trabajos_activos", 0)
                    capacidad_total += estado.get("capacidad_maxima", 0)
                    capacidad_usada += estado.get("trabajos_activos", 0)
            
            return {
                "total_nodos": total_nodos,
                "nodos_activos": nodos_activos,
                "nodos_inactivos": total_nodos - nodos_activos,
                "trabajos_en_proceso": trabajos_totales,
                "capacidad_total": capacidad_total,
                "capacidad_usada": capacidad_usada,
                "capacidad_disponible": capacidad_total - capacidad_usada,
                "porcentaje_uso": round(
                    (capacidad_usada / capacidad_total * 100) if capacidad_total > 0 else 0,
                    2
                ),
                "nodos": detalles_nodos
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estado del cluster: {e}")
            return {
                "total_nodos": 0,
                "nodos_activos": 0,
                "error": str(e)
            }