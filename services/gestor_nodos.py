import Pyro5.api
import threading
import time
from typing import List, Dict, Any, Optional
from database import get_db_servidor
from models.nodo import Nodo
from config import config
from utils.logger import get_logger

logger = get_logger("GestorNodosCorregido")

class GestorNodosImpl:
    def __init__(self):
        self.nodos_registrados: Dict[str, Any] = {}
        self.lock = threading.Lock()
        self._inicializar_gestor()
    
    def _inicializar_gestor(self):
        """Inicializa el gestor de nodos"""
        try:
            logger.info("Inicializando gestor de nodos...")
            self._descubrir_nodos_existentes()
        except Exception as e:
            logger.error(f"Error inicializando gestor de nodos: {e}")
    
    def _descubrir_nodos_existentes(self):
        """Descubre nodos ya registrados en el NameServer"""
        try:
            ns = Pyro5.api.locate_ns(host="localhost", port=config.pyro.ns_port)
            nodos_en_ns = ns.list(prefix="nodo.")
            
            logger.info(f"Encontrados {len(nodos_en_ns)} nodos en NameServer")
            
            for nombre_nodo, uri in nodos_en_ns.items():
                id_nodo = nombre_nodo.replace("nodo.", "")
                try:
                    # Configurar proxy con timeout
                    proxy = Pyro5.api.Proxy(uri)
                    proxy._pyroTimeout = 5
                    
                    # Probar conexión
                    estado = proxy.obtener_estado()
                    
                    with self.lock:
                        self.nodos_registrados[id_nodo] = {
                            'proxy': proxy,
                            'uri': uri,
                            'estado': estado,
                            'ultima_comprobacion': time.time(),
                            'activo': True
                        }
                    
                    logger.info(f"Nodo descubierto y activo: {id_nodo}")
                    
                except Exception as e:
                    logger.warning(f"Nodo {id_nodo} no responde: {e}")
                    with self.lock:
                        self.nodos_registrados[id_nodo] = {
                            'uri': uri,
                            'activo': False,
                            'ultima_comprobacion': time.time(),
                            'error': str(e)
                        }
                    
        except Exception as e:
            logger.error(f"Error descubriendo nodos existentes: {e}")
    
    def obtener_nodo_disponible(self) -> Optional[Dict[str, Any]]:
        """Obtiene un nodo disponible de los ya registrados - VERSIÓN CORREGIDA"""
        try:
            logger.info("Buscando nodo disponible...")
            self._actualizar_estado_nodos()
            
            nodos_activos = []
            for id_nodo, info in self.nodos_registrados.items():
                if info.get('activo', False):
                    estado = info.get('estado', {})
                    trabajos_activos = estado.get('trabajos_activos', 0)
                    
                    if trabajos_activos < 5:  # Límite de trabajos por nodo
                        nodos_activos.append({
                            'id_nodo': id_nodo,
                            'proxy': info['proxy'],
                            'uri': info['uri'],
                            'estado_actual': info['estado'],
                            'trabajos_activos': trabajos_activos
                        })
            
            if nodos_activos:
                # Ordenar por menor carga de trabajo
                nodos_activos.sort(key=lambda x: x['trabajos_activos'])
                mejor_nodo = nodos_activos[0]
                logger.info(f"Nodo disponible encontrado: {mejor_nodo['id_nodo']} (trabajos: {mejor_nodo['trabajos_activos']})")
                return mejor_nodo
            else:
                logger.warning("No hay nodos disponibles")
                return None
            
        except Exception as e:
            logger.error(f"Error obteniendo nodo disponible: {e}")
            return None
    
    def _actualizar_estado_nodos(self):
        """Actualiza el estado de todos los nodos registrados"""
        with self.lock:
            for id_nodo, info in self.nodos_registrados.items():
                try:
                    if 'proxy' in info:
                        # Verificar si el nodo sigue activo
                        estado_actual = info['proxy'].obtener_estado()
                        info['estado'] = estado_actual
                        info['ultima_comprobacion'] = time.time()
                        info['activo'] = True
                        logger.debug(f"Nodo {id_nodo} actualizado: {estado_actual}")
                    else:
                        # Intentar reconectar
                        try:
                            ns = Pyro5.api.locate_ns(host="localhost", port=config.pyro.ns_port)
                            uri = ns.lookup(f"nodo.{id_nodo}")
                            proxy = Pyro5.api.Proxy(uri)
                            proxy._pyroTimeout = 5
                            estado = proxy.obtener_estado()
                            
                            info.update({
                                'proxy': proxy,
                                'uri': uri,
                                'estado': estado,
                                'ultima_comprobacion': time.time(),
                                'activo': True
                            })
                            logger.info(f"Nodo {id_nodo} reconectado exitosamente")
                        except Exception as e:
                            info['activo'] = False
                            logger.warning(f"No se pudo reconectar con nodo {id_nodo}: {e}")
                            
                except Exception as e:
                    logger.warning(f"Nodo {id_nodo} no responde: {e}")
                    info['activo'] = False
    
    def obtener_estado_nodos(self) -> List[Dict[str, Any]]:
        """Obtiene el estado de todos los nodos"""
        try:
            self._actualizar_estado_nodos()
            
            nodos_info = []
            for id_nodo, info in self.nodos_registrados.items():
                nodo_info = {
                    'id_nodo': id_nodo,
                    'ip': info.get('ip', 'Desconocida'),
                    'activo': info.get('activo', False),
                    'ultima_comprobacion': info.get('ultima_comprobacion', 0)
                }
                
                if 'estado' in info:
                    nodo_info.update(info['estado'])
                
                nodos_info.append(nodo_info)
            
            return nodos_info
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de nodos: {e}")
            return []
    
    def ejecutar_trabajo_en_nodo(self, trabajo: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta un trabajo en un nodo disponible"""
        nodo_info = self.obtener_nodo_disponible()
        
        if not nodo_info:
            return {
                'exito': False,
                'error': 'No hay nodos workers disponibles'
            }
        
        try:
            # Configurar timeout para la llamada remota
            nodo_info['proxy']._pyroTimeout = 30
            
            logger.info(f"Ejecutando trabajo {trabajo['id_trabajo']} en nodo {nodo_info['id_nodo']}")
            
            resultado = nodo_info['proxy'].procesar(
                id_trabajo=trabajo['id_trabajo'],
                ruta_entrada=trabajo['ruta_entrada'],
                ruta_salida=trabajo['ruta_salida'],
                lista_transformaciones=trabajo['transformaciones']
            )
            
            logger.info(f"Trabajo {trabajo['id_trabajo']} ejecutado en nodo {nodo_info['id_nodo']}")
            return resultado
            
        except Exception as e:
            logger.error(f"Error ejecutando trabajo en nodo {nodo_info['id_nodo']}: {e}")
            # Marcar nodo como inactivo
            with self.lock:
                if nodo_info['id_nodo'] in self.nodos_registrados:
                    self.nodos_registrados[nodo_info['id_nodo']]['activo'] = False
            
            return {
                'exito': False,
                'error': f"Error en nodo {nodo_info['id_nodo']}: {str(e)}"
            }