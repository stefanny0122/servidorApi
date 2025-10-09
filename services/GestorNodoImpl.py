"""
Implementación del gestor de nodos para el servidor FastAPI
CON TRANSFERENCIA DE ARCHIVOS
"""

from typing import Dict, Any, List, Optional
from utils.logger import get_logger
from services.ClienteNodoWorker import BalanceadorCargaNodos

logger = get_logger("GestorNodosImpl")

class GestorNodosImpl:
    """
    Gestor de nodos para el servidor FastAPI.
    Encapsula la lógica de comunicación con nodos workers.
    """
    
    def __init__(self):
        self.balanceador = BalanceadorCargaNodos()
        self.cliente = self.balanceador.cliente
    
    def ejecutar_trabajo_en_nodo(self, trabajo: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta un trabajo en un nodo disponible CON TRANSFERENCIA DE ARCHIVOS.
        
        Args:
            trabajo: Dict con datos del trabajo
            
        Returns:
            Resultado del procesamiento
        """
        try: 
            id_nodo = self.balanceador.obtener_nodo_optimo()
            
            if not id_nodo:
                return {
                    "exito": False,
                    "error": "No hay nodos disponibles",
                    "id_trabajo": trabajo.get('id_trabajo', 'desconocido')
                }
         
            resultado = self.cliente.enviar_trabajo_con_archivos(
                id_nodo=id_nodo,
                id_trabajo=trabajo['id_trabajo'],
                ruta_entrada=trabajo['ruta_entrada'],
                ruta_salida=trabajo['ruta_salida'],
                transformaciones=trabajo['transformaciones']
            )
            
            return resultado
            
        except Exception as e:
            logger.error(f"Error ejecutando trabajo {trabajo.get('id_trabajo')}: {e}")
            return {
                "exito": False,
                "error": str(e),
                "id_trabajo": trabajo.get('id_trabajo', 'desconocido')
            }
    
    def obtener_estado_nodos(self) -> List[Dict[str, Any]]:
        """Obtiene el estado de todos los nodos"""
        estado_cluster = self.balanceador.obtener_estado_cluster()
        return estado_cluster.get('nodos', [])
    
    def obtener_nodo_disponible(self) -> Optional[Dict[str, Any]]:
        """Obtiene un nodo disponible"""
        id_nodo = self.balanceador.obtener_nodo_optimo()
        if id_nodo: 
            estado = self.cliente.obtener_estado_nodo(id_nodo)
            if estado:
                return {
                    "id_nodo": id_nodo,
                    "estado": estado.get("estado", "desconocido"),
                    "capacidad_disponible": estado.get("capacidad_disponible", 0),
                    "trabajos_activos": estado.get("trabajos_activos", 0)
                }
        return None
    
    def registrar_nodo(self, ip: str, descripcion: str, capacidad_total: int) -> bool:
        """
        Registra un nuevo nodo (para uso futuro con base de datos)
        Por ahora, los nodos se registran automáticamente con Pyro5
        """
        logger.info(f"Nodo registrado - IP: {ip}, Desc: {descripcion}, Capacidad: {capacidad_total}")
        return True
    
    def actualizar_estado_nodo(self, id_nodo: int, estado: str, capacidad_usada: int) -> bool:
        """
        Actualiza estado de nodo (para uso futuro con base de datos)
        """
        logger.info(f"Actualizando nodo {id_nodo} - Estado: {estado}, Capacidad usada: {capacidad_usada}")
        return True