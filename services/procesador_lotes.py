import uuid
import os
import threading
from typing import List, Dict, Any
from datetime import datetime
from database import get_db_servidor, get_db_cliente
from models.lote_procesamiento import SolicitudServidor
from models.imagen import ImagenServidor
from models.transformacion import Transformacion
from models.cliente_models import SolicitudCliente, ImagenCliente
from config import config
from utils.logger import get_logger
from services.gestor_nodos import GestorNodosImpl

logger = get_logger("ProcesadorLotesCorregido")

class ProcesadorLotesImpl:
    def __init__(self):
        self.gestor_nodos = GestorNodosImpl()
        self.lock = threading.Lock()
    
    def crear_solicitud_procesamiento(self, id_usuario: int, imagenes: List[Dict]) -> Dict[str, Any]:
        """Crea una nueva solicitud de procesamiento de lote - VERSIÓN CORREGIDA"""
        try:
            logger.info(f"Creando solicitud de procesamiento para usuario {id_usuario}, {len(imagenes)} imágenes")
            
            with get_db_servidor() as db_servidor:
                # Crear solicitud en servidor
                solicitud_servidor = SolicitudServidor(
                    id_usuario=id_usuario,
                    estado='procesando'
                )
                db_servidor.add(solicitud_servidor)
                db_servidor.flush()
                
                # Crear solicitud en cliente
                with get_db_cliente() as db_cliente:
                    solicitud_cliente = SolicitudCliente(
                        id_usuario=id_usuario,
                        estado='procesando'
                    )
                    db_cliente.add(solicitud_cliente)
                    db_cliente.commit()
                
                # Procesar cada imagen
                resultados = []
                hilos = []
                
                for i, img_data in enumerate(imagenes):
                    # Guardar información de la imagen en BD
                    imagen_servidor = ImagenServidor(
                        id_solicitud=solicitud_servidor.id_solicitud,
                        nombre_original=img_data['nombre_original'],
                        formato_original=img_data['formato_original'],
                        ruta_origen=img_data['ruta_temporal'],
                        estado='procesando'
                    )
                    db_servidor.add(imagen_servidor)
                    db_servidor.flush()
                    
                    # Guardar transformaciones en BD (solo para registro)
                    for j, transformacion in enumerate(img_data['transformaciones']):
                        trans = Transformacion(
                            id_imagen=imagen_servidor.id_imagen,
                            tipo=transformacion['tipo'],
                            parametros=str(transformacion.get('parametros', {})),
                            orden=j
                        )
                        db_servidor.add(trans)
                    
                    # Procesar imagen en hilo separado
                    hilo = threading.Thread(
                        target=self._procesar_imagen_thread,
                        args=(imagen_servidor.id_imagen, img_data, resultados)
                    )
                    hilos.append(hilo)
                    hilo.start()
                
                # Esperar a que todos los hilos terminen
                for hilo in hilos:
                    hilo.join()
                
                # Actualizar estado de la solicitud basado en resultados
                procesamientos_exitosos = sum(1 for r in resultados if r.get('exito', False))
                
                if procesamientos_exitosos == len(imagenes):
                    estado_final = 'completado'
                    mensaje = "Todas las imágenes procesadas exitosamente"
                elif procesamientos_exitosos > 0:
                    estado_final = 'parcial'
                    mensaje = f"{procesamientos_exitosos}/{len(imagenes)} imágenes procesadas exitosamente"
                else:
                    estado_final = 'fallido'
                    mensaje = "No se pudo procesar ninguna imagen"
                
                solicitud_servidor.estado = estado_final
                solicitud_cliente.estado = estado_final
                solicitud_servidor.fecha_completado = datetime.now()
                solicitud_cliente.fecha_completado = datetime.now()
                
                db_servidor.commit()
                
                logger.info(f"Solicitud {solicitud_servidor.id_solicitud} procesada: {mensaje}")
                
                return {
                    'id_solicitud': solicitud_servidor.id_solicitud,
                    'estado': estado_final,
                    'imagenes_procesadas': len(imagenes),
                    'imagenes_exitosas': procesamientos_exitosos,
                    'mensaje': mensaje,
                    'fecha_envio': datetime.now().isoformat()
                }
            
        except Exception as e:
            logger.error(f"Error creando solicitud: {e}")
            return {
                'error': str(e),
                'estado': 'error'
            }
    
    def _procesar_imagen_thread(self, id_imagen: int, img_data: Dict, resultados: List):
        """Procesa una imagen en un hilo separado delegando al nodo worker"""
        try:
            # Crear trabajo para el nodo worker
            trabajo = {
                'id_trabajo': f"img_{id_imagen}",
                'ruta_entrada': img_data['ruta_temporal'],
                'ruta_salida': os.path.join(config.results_dir, f"resultado_{id_imagen}.png"),
                'transformaciones': img_data['transformaciones']
            }
            
            # Ejecutar en nodo disponible
            resultado = self.gestor_nodos.ejecutar_trabajo_en_nodo(trabajo)
            
            # Actualizar base de datos con el resultado
            with get_db_servidor() as db:
                imagen = db.query(ImagenServidor).filter(ImagenServidor.id_imagen == id_imagen).first()
                if imagen:
                    if resultado.get('exito', False):
                        imagen.estado = 'procesada'
                        imagen.ruta_resultado = resultado.get('ruta_resultado', '')
                    else:
                        imagen.estado = 'error'
                        logger.error(f"Imagen {id_imagen} falló: {resultado.get('error', 'Error desconocido')}")
                    imagen.fecha_procesado = datetime.now()
                    db.commit()
            
            resultados.append(resultado)
            
        except Exception as e:
            logger.error(f"Error en hilo de procesamiento para imagen {id_imagen}: {e}")
            resultados.append({'exito': False, 'error': str(e)})