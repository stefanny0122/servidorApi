"""
Servicio para procesar lotes donde cada imagen tiene transformaciones específicas
Desglosa el lote y procesa cada imagen con sus propias especificaciones
"""
import os
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from database import get_db_servidor, get_db_cliente
from models.imagen_individual import ProcesamientoIndividual, ProcesamientoIndividualCliente
from services.GestorNodoImpl import GestorNodosImpl
from config import config
from utils.logger import get_logger

logger = get_logger("ProcesadorLoteIndividual")


class ProcesadorLoteIndividual:
    """
    Procesa lotes de imágenes donde cada una tiene transformaciones específicas.
    
    Flujo:
    1. Recibe lote con N imágenes
    2. Cada imagen tiene sus propias transformaciones
    3. Desglosa el lote en N procesamientos individuales
    4. Procesa cada imagen en paralelo con sus specs
    5. Consolida resultados del lote completo
    """
    
    def __init__(self, max_workers: int = 10):
        self.gestor_nodos = GestorNodosImpl()
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="LoteIndividualProcessor"
        )
        self.lotes_activos = {}  # Cache de estado de lotes
        logger.info(f"ProcesadorLoteIndividual iniciado con {max_workers} workers")
    
    def procesar_lote(
        self,
        id_lote: str,
        id_usuario: int,
        imagenes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Procesa un lote completo desglosándolo en procesamientos individuales.
        
        Args:
            id_lote: ID único del lote
            id_usuario: ID del usuario
            imagenes: Lista de imágenes con sus transformaciones específicas
                Formato: [
                    {
                        'nombre_original': 'foto1.jpg',
                        'ruta_temporal': '/path/to/foto1.jpg',
                        'transformaciones': [...],
                        'tamanio_bytes': 1024,
                        ...
                    },
                    ...
                ]
        
        Returns:
            Dict con información del lote procesado
        """
        try:
            logger.info(
                f"[Lote {id_lote}] Iniciando procesamiento de {len(imagenes)} imágenes "
                f"con especificaciones individuales"
            )
            
            # Crear registros individuales para cada imagen
            ids_procesamiento = self._crear_registros_individuales(
                id_lote=id_lote,
                id_usuario=id_usuario,
                imagenes=imagenes
            )
            
            # Inicializar estado del lote
            self.lotes_activos[id_lote] = {
                'id_usuario': id_usuario,
                'total_imagenes': len(imagenes),
                'ids_procesamiento': ids_procesamiento,
                'estado': 'procesando',
                'fecha_inicio': datetime.now()
            }
            
            # Procesar todas las imágenes en paralelo
            self.executor.submit(
                self._procesar_lote_async,
                id_lote,
                ids_procesamiento,
                imagenes
            )
            
            return {
                'ids_procesamiento': ids_procesamiento,
                'total_imagenes': len(imagenes)
            }
            
        except Exception as e:
            logger.error(f"[Lote {id_lote}] Error creando procesamiento: {e}", exc_info=True)
            raise
    
    def _crear_registros_individuales(
        self,
        id_lote: str,
        id_usuario: int,
        imagenes: List[Dict]
    ) -> List[int]:
        """Crea un registro de procesamiento individual para cada imagen del lote"""
        db_servidor = None
        db_cliente = None
        ids_procesamiento = []
        
        try:
            db_servidor = next(get_db_servidor())
            db_cliente = next(get_db_cliente())
            
            for imagen in imagenes:
                # Crear en servidor
                procesamiento_srv = ProcesamientoIndividual(
                    id_usuario=id_usuario,
                    nombre_original=imagen['nombre_original'],
                    formato_original=imagen['formato_original'],
                    ruta_entrada=imagen['ruta_temporal'],
                    transformaciones=imagen['transformaciones'],
                    tamanio_entrada_bytes=imagen['tamanio_bytes'],
                    estado='pendiente'
                )
                db_servidor.add(procesamiento_srv)
                db_servidor.flush()
                
                ids_procesamiento.append(procesamiento_srv.id_procesamiento)
                
                # Crear en cliente
                procesamiento_cli = ProcesamientoIndividualCliente(
                    id_usuario=id_usuario,
                    nombre_original=imagen['nombre_original'],
                    formato_original=imagen['formato_original'],
                    estado='pendiente'
                )
                db_cliente.add(procesamiento_cli)
                
                logger.debug(
                    f"[Lote {id_lote}] Registro creado para '{imagen['nombre_original']}' - "
                    f"ID: {procesamiento_srv.id_procesamiento}, "
                    f"{len(imagen['transformaciones'])} transformaciones"
                )
            
            db_servidor.commit()
            db_cliente.commit()
            
            logger.info(
                f"[Lote {id_lote}] {len(ids_procesamiento)} registros individuales creados"
            )
            
            return ids_procesamiento
            
        except Exception as e:
            logger.error(f"Error creando registros individuales: {e}")
            if db_servidor:
                db_servidor.rollback()
            if db_cliente:
                db_cliente.rollback()
            raise
        finally:
            if db_servidor:
                db_servidor.close()
            if db_cliente:
                db_cliente.close()
    
    def _procesar_lote_async(
        self,
        id_lote: str,
        ids_procesamiento: List[int],
        imagenes: List[Dict]
    ):
        """
        Procesa todas las imágenes del lote en paralelo.
        Corre en un thread del executor.
        """
        try:
            logger.info(f"[Lote {id_lote}] Iniciando procesamiento paralelo de {len(imagenes)} imágenes")
            
            # Crear futures para cada imagen
            futures = {}
            for id_proc, imagen in zip(ids_procesamiento, imagenes):
                future = self.executor.submit(
                    self._procesar_imagen_individual,
                    id_lote,
                    id_proc,
                    imagen
                )
                futures[future] = (id_proc, imagen['nombre_original'])
            
            # Recoger resultados
            completados = 0
            errores = 0
            
            try:
                for future in as_completed(futures, timeout=3600):  # 1 hora timeout
                    id_proc, nombre = futures[future]
                    try:
                        resultado = future.result()
                        if resultado.get('exito'):
                            completados += 1
                            logger.info(
                                f"[Lote {id_lote}] ✓ {nombre} completado "
                                f"({completados + errores}/{len(imagenes)})"
                            )
                        else:
                            errores += 1
                            logger.error(
                                f"[Lote {id_lote}] ✗ {nombre} falló: "
                                f"{resultado.get('error', 'Error desconocido')}"
                            )
                    except Exception as e:
                        errores += 1
                        logger.error(f"[Lote {id_lote}] ✗ {nombre} excepción: {e}")
            except TimeoutError:
                logger.error(f"[Lote {id_lote}] Timeout en procesamiento paralelo")
                # Marcar todos los pendientes como error
                for future in futures:
                    if not future.done():
                        id_proc, nombre = futures[future]
                        self._actualizar_estado(id_proc, 'error', 'Timeout en procesamiento')
                        errores += 1
            
            # Actualizar estado del lote
            if completados == len(imagenes):
                estado_final = 'completado'
            elif completados > 0:
                estado_final = 'parcial'
            else:
                estado_final = 'fallido'
            
            if id_lote in self.lotes_activos:
                self.lotes_activos[id_lote]['estado'] = estado_final
                self.lotes_activos[id_lote]['completados'] = completados
                self.lotes_activos[id_lote]['errores'] = errores
                self.lotes_activos[id_lote]['fecha_fin'] = datetime.now()
            
            logger.info(
                f"[Lote {id_lote}] Procesamiento finalizado - "
                f"Estado: {estado_final}, Exitosos: {completados}/{len(imagenes)}"
            )
            
        except Exception as e:
            logger.error(f"[Lote {id_lote}] Error en procesamiento asíncrono: {e}", exc_info=True)
            if id_lote in self.lotes_activos:
                self.lotes_activos[id_lote]['estado'] = 'error'
    
    def _procesar_imagen_individual(
        self,
        id_lote: str,
        id_procesamiento: int,
        imagen: Dict
    ) -> Dict:
        """
        Procesa una imagen individual con sus transformaciones específicas.
        Cada invocación corre en su propio thread.
        """
        db = None
        try:
            logger.info(
                f"[Lote {id_lote}] Procesando '{imagen['nombre_original']}' - "
                f"ID {id_procesamiento}"
            )
            
            # Actualizar a 'procesando'
            self._actualizar_estado(id_procesamiento, 'procesando')
            
            # Generar ruta de salida
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_id = uuid.uuid4().hex[:8]
            nombre_base = os.path.splitext(imagen['nombre_original'])[0]
            ruta_salida = os.path.join(
                config.results_dir,
                f"lote_{id_lote}",
                f"{timestamp}_{random_id}_{nombre_base}_procesado.png"
            )
            
            # CREAR DIRECTORIO SI NO EXISTE
            os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
            
            # Preparar trabajo para el nodo
            trabajo = {
                'id_trabajo': f"lote_{id_lote}_img_{id_procesamiento}",
                'ruta_entrada': imagen['ruta_temporal'],
                'ruta_salida': ruta_salida,
                'transformaciones': imagen['transformaciones']
            }
            
            # Ejecutar en nodo worker
            inicio = datetime.now()
            resultado = self.gestor_nodos.ejecutar_trabajo_en_nodo(trabajo)
            fin = datetime.now()
            
            tiempo_segundos = int((fin - inicio).total_seconds())
            
            # Actualizar BD con resultado
            db = next(get_db_servidor())
            procesamiento = db.query(ProcesamientoIndividual).filter(
                ProcesamientoIndividual.id_procesamiento == id_procesamiento
            ).first()
            
            if procesamiento:
                if resultado.get('exito', False):
                    procesamiento.estado = 'completado'
                    procesamiento.ruta_resultado = resultado.get('ruta_resultado', ruta_salida)
                    
                    if os.path.exists(procesamiento.ruta_resultado):
                        procesamiento.tamanio_resultado_bytes = os.path.getsize(
                            procesamiento.ruta_resultado
                        )
                        procesamiento.formato_salida = 'png'
                    
                    procesamiento.id_nodo = resultado.get('nodo', 'desconocido')
                    procesamiento.tiempo_procesamiento_segundos = tiempo_segundos
                else:
                    procesamiento.estado = 'error'
                    procesamiento.mensaje_error = resultado.get('error', 'Error desconocido')
                
                procesamiento.fecha_completado = datetime.now()
                db.commit()
            
            # Actualizar cliente
            self._actualizar_cliente(
                id_procesamiento,
                procesamiento.estado,
                procesamiento.ruta_resultado if resultado.get('exito') else None
            )
            
            # Limpiar archivo temporal después del procesamiento exitoso
            if resultado.get('exito', False):
                self._limpiar_archivos_temporales(imagen['ruta_temporal'])
            
            return {
                'id_procesamiento': id_procesamiento,
                'exito': resultado.get('exito', False),
                'error': resultado.get('error')
            }
            
        except Exception as e:
            logger.error(
                f"[Lote {id_lote}] Error procesando imagen {id_procesamiento}: {e}",
                exc_info=True
            )
            self._actualizar_estado(id_procesamiento, 'error', str(e))
            return {
                'id_procesamiento': id_procesamiento,
                'exito': False,
                'error': str(e)
            }
        finally:
            if db:
                db.close()
    
    def _limpiar_archivos_temporales(self, ruta_temporal: str):
        """Limpia archivos temporales después del procesamiento"""
        try:
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)
                logger.debug(f"Archivo temporal eliminado: {ruta_temporal}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo temporal {ruta_temporal}: {e}")
    
    def _actualizar_estado(
        self,
        id_procesamiento: int,
        estado: str,
        mensaje_error: Optional[str] = None
    ):
        """Actualiza el estado de un procesamiento individual"""
        db = None
        try:
            db = next(get_db_servidor())
            
            procesamiento = db.query(ProcesamientoIndividual).filter(
                ProcesamientoIndividual.id_procesamiento == id_procesamiento
            ).first()
            
            if procesamiento:
                procesamiento.estado = estado
                
                if estado == 'procesando' and not procesamiento.fecha_inicio_procesamiento:
                    procesamiento.fecha_inicio_procesamiento = datetime.now()
                
                if estado in ['completado', 'error'] and not procesamiento.fecha_completado:
                    procesamiento.fecha_completado = datetime.now()
                
                if mensaje_error:
                    procesamiento.mensaje_error = mensaje_error
                
                db.commit()
            
        except Exception as e:
            logger.error(f"Error actualizando estado de procesamiento {id_procesamiento}: {e}")
        finally:
            if db:
                db.close()
    
    def _actualizar_cliente(
        self,
        id_procesamiento: int,
        estado: str,
        ruta_resultado: Optional[str] = None
    ):
        """Actualiza el registro en la BD del cliente"""
        db = None
        try:
            db = next(get_db_cliente())
            
            procesamiento = db.query(ProcesamientoIndividualCliente).filter(
                ProcesamientoIndividualCliente.id_procesamiento == id_procesamiento
            ).first()
            
            if procesamiento:
                procesamiento.estado = estado
                if ruta_resultado:
                    procesamiento.ruta_resultado = ruta_resultado
                if estado in ['completado', 'error']:
                    procesamiento.fecha_completado = datetime.now()
                
                db.commit()
            
        except Exception as e:
            logger.error(f"Error actualizando cliente para procesamiento {id_procesamiento}: {e}")
        finally:
            if db:
                db.close()
    
    def _obtener_ids_procesamiento_por_lote(self, id_lote: str, id_usuario: int) -> List[int]:
        """Obtiene IDs de procesamiento desde BD cuando no están en cache"""
        db = None
        try:
            db = next(get_db_servidor())
            # Buscar procesamientos por patrón en ruta_entrada
            procesamientos = db.query(ProcesamientoIndividual).filter(
                ProcesamientoIndividual.id_usuario == id_usuario,
                ProcesamientoIndividual.ruta_entrada.like(f"%lote_{id_lote}%")
            ).all()
            
            return [p.id_procesamiento for p in procesamientos]
        finally:
            if db:
                db.close()
    
    def obtener_estado_lote(self, id_lote: str, id_usuario: int) -> Optional[Dict]:
        """
        Obtiene el estado consolidado de un lote.
        Consulta el estado de cada imagen individual.
        """
        db = None
        try:
            # Verificar cache primero
            if id_lote in self.lotes_activos:
                cache = self.lotes_activos[id_lote]
                if cache['id_usuario'] != id_usuario:
                    return None
                ids_procesamiento = cache['ids_procesamiento']
            else:
                # Buscar en BD si no está en cache
                ids_procesamiento = self._obtener_ids_procesamiento_por_lote(id_lote, id_usuario)
                if not ids_procesamiento:
                    return None
            
            # Obtener estado de cada imagen
            db = next(get_db_servidor())
            procesamientos = db.query(ProcesamientoIndividual).filter(
                ProcesamientoIndividual.id_procesamiento.in_(ids_procesamiento)
            ).all()
            
            if not procesamientos:
                return None
            
            # Consolidar estados
            total = len(procesamientos)
            completados = sum(1 for p in procesamientos if p.estado == 'completado')
            errores = sum(1 for p in procesamientos if p.estado == 'error')
            procesando = sum(1 for p in procesamientos if p.estado == 'procesando')
            pendientes = sum(1 for p in procesamientos if p.estado == 'pendiente')
            
            # Determinar estado general
            if completados == total:
                estado_general = 'completado'
            elif errores == total:
                estado_general = 'fallido'
            elif completados > 0 or errores > 0:
                estado_general = 'procesando'
            else:
                estado_general = 'pendiente'
            
            return {
                'id_lote': id_lote,
                'estado': estado_general,
                'total_imagenes': total,
                'completados': completados,
                'errores': errores,
                'procesando': procesando,
                'pendientes': pendientes,
                'progreso_porcentaje': round((completados / total * 100) if total > 0 else 0, 2),
                'fecha_inicio': procesamientos[0].fecha_creacion.isoformat() if procesamientos else None
            }
            
        finally:
            if db:
                db.close()
    
    def obtener_detalle_imagenes(self, id_lote: str, id_usuario: int) -> Optional[Dict]:
        """
        Obtiene el detalle de cada imagen del lote con sus transformaciones específicas.
        """
        db = None
        try:
            # Obtener IDs del lote
            if id_lote not in self.lotes_activos:
                # Intentar buscar en BD
                ids_procesamiento = self._obtener_ids_procesamiento_por_lote(id_lote, id_usuario)
                if not ids_procesamiento:
                    return None
            else:
                cache = self.lotes_activos[id_lote]
                if cache['id_usuario'] != id_usuario:
                    return None
                ids_procesamiento = cache['ids_procesamiento']
            
            # Obtener detalles
            db = next(get_db_servidor())
            procesamientos = db.query(ProcesamientoIndividual).filter(
                ProcesamientoIndividual.id_procesamiento.in_(ids_procesamiento)
            ).order_by(ProcesamientoIndividual.fecha_creacion).all()
            
            if not procesamientos:
                return None
            
            imagenes_detalle = []
            for proc in procesamientos:
                imagenes_detalle.append({
                    'id_procesamiento': proc.id_procesamiento,
                    'nombre_original': proc.nombre_original,
                    'formato_original': proc.formato_original,
                    'estado': proc.estado,
                    'transformaciones': proc.transformaciones,
                    'num_transformaciones': len(proc.transformaciones) if isinstance(proc.transformaciones, list) else 0,
                    'ruta_resultado': proc.ruta_resultado,
                    'tamanio_entrada_kb': round(proc.tamanio_entrada_bytes / 1024, 2) if proc.tamanio_entrada_bytes else None,
                    'tamanio_resultado_kb': round(proc.tamanio_resultado_bytes / 1024, 2) if proc.tamanio_resultado_bytes else None,
                    'tiempo_procesamiento': proc.tiempo_procesamiento_segundos,
                    'nodo': proc.id_nodo,
                    'error': proc.mensaje_error,
                    'fecha_creacion': proc.fecha_creacion.isoformat() if proc.fecha_creacion else None,
                    'fecha_completado': proc.fecha_completado.isoformat() if proc.fecha_completado else None
                })
            
            return {
                'id_lote': id_lote,
                'imagenes': imagenes_detalle,
                'total': len(imagenes_detalle)
            }
            
        finally:
            if db:
                db.close()
    
    def obtener_historial_usuario(
        self,
        usuario_id: int,
        limite: int = 10,
        offset: int = 0
    ) -> List[Dict]:
        """
        Obtiene el historial de lotes del usuario.
        Agrupa los procesamientos individuales por lote.
        """
        db = None
        try:
            # Obtener todos los procesamientos del usuario
            db = next(get_db_servidor())
            
            procesamientos = db.query(ProcesamientoIndividual).filter(
                ProcesamientoIndividual.id_usuario == usuario_id
            ).order_by(
                ProcesamientoIndividual.fecha_creacion.desc()
            ).all()
            
            # Agrupar por lote usando cache y BD
            lotes_hist = []
            
            # Primero buscar en cache
            for id_lote, info in self.lotes_activos.items():
                if info['id_usuario'] == usuario_id:
                    # Obtener procesamientos de este lote
                    lote_procs = [p for p in procesamientos 
                                  if p.id_procesamiento in info['ids_procesamiento']]
                    
                    if lote_procs:
                        completados = sum(1 for p in lote_procs if p.estado == 'completado')
                        errores = sum(1 for p in lote_procs if p.estado == 'error')
                        
                        lotes_hist.append({
                            'id_lote': id_lote,
                            'total_imagenes': len(lote_procs),
                            'completados': completados,
                            'errores': errores,
                            'estado': info['estado'],
                            'fecha_inicio': info['fecha_inicio'].isoformat(),
                            'fecha_fin': info.get('fecha_fin').isoformat() if info.get('fecha_fin') else None
                        })
            
            # Ordenar por fecha
            lotes_hist.sort(key=lambda x: x['fecha_inicio'], reverse=True)
            
            # Paginar
            return lotes_hist[offset:offset + limite]
            
        finally:
            if db:
                db.close()
    
    def shutdown(self):
        """Cierra el executor de forma ordenada"""
        logger.info("Cerrando ProcesadorLoteIndividual...")
        self.executor.shutdown(wait=True)
        logger.info("ProcesadorLoteIndividual cerrado")