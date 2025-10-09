import requests
import time
import Pyro5.api
import subprocess
import sys
import os
from PIL import Image
import io
 
BASE_URL = "http://localhost:8080"
RUTA_NODOS = r"D:\Nodos"  

class TestSistemaUnificado:
    def __init__(self):
        self.token = None
        self.headers = None
        self.worker_process = None
        
    def verificar_rutas(self):
        """Verificar que todas las rutas necesarias existen"""
        print("VERIFICANDO RUTAS DEL SISTEMA...")
        
        rutas_verificar = [
            (RUTA_NODOS, "Directorio de nodos"),
            (os.path.join(RUTA_NODOS, "nodo_worker.py"), "Archivo nodo_worker.py"),
            (os.path.join(RUTA_NODOS, "procesador_imagen.py"), "Archivo procesador_imagen.py"),
            (os.path.join(RUTA_NODOS, "transformaciones"), "Directorio de transformaciones")
        ]
        
        todas_ok = True
        for ruta, descripcion in rutas_verificar:
            if os.path.exists(ruta):
                print(f"   OK - {descripcion}: {ruta}")
            else:
                print(f"   ERROR - {descripcion} no encontrado: {ruta}")
                todas_ok = False
        
        return todas_ok
    
    def login(self):
        """Obtener token de autenticación"""
        print("1. INICIANDO SESIÓN...")
        login_data = {
            "email": "admin@example.com",
            "password": "Admin123!",
            "tipo": "servidor"
        }
        
        try:
            response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
            if response.status_code == 200:
                self.token = response.json()['access_token']
                self.headers = {"Authorization": f"Bearer {self.token}"}
                print("   OK - Login exitoso")
                return True
            else:
                print(f"   ERROR - Error en login: {response.text}")
                return False
        except Exception as e:
            print(f"   ERROR - No se pudo conectar al servidor: {e}")
            return False
    
    def iniciar_nodo_worker(self):
        """Iniciar nodo worker desde la ruta correcta"""
        print("2. INICIANDO NODO WORKER...")
        
        ruta_nodo_worker = os.path.join(RUTA_NODOS, "nodo_worker.py")
        
        if not os.path.exists(ruta_nodo_worker):
            print(f"   ERROR - Archivo no encontrado: {ruta_nodo_worker}")
            return False
        
        try:
            self.worker_process = subprocess.Popen([
                sys.executable, "nodo_worker.py", "worker01"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
            cwd=RUTA_NODOS)   
            
            time.sleep(3)
            
            if self.worker_process.poll() is not None:
                stdout, stderr = self.worker_process.communicate()
                print(f"   ERROR - Nodo worker falló al iniciar")
                if stdout:
                    print(f"   STDOUT: {stdout}")
                if stderr:
                    print(f"   STDERR: {stderr}")
                return False
                
            print("   OK - Nodo worker iniciado")
            return True
            
        except Exception as e:
            print(f"   ERROR - Error iniciando nodo worker: {e}")
            return False
    
    def verificar_nameserver(self):
        """Verificar que NameServer esté corriendo"""
        print("3. VERIFICANDO NAMESERVER...")
        try:
            ns = Pyro5.api.locate_ns(host="localhost", port=9090)
            print("   OK - NameServer encontrado")
            return True
        except Exception as e:
            print(f"   ERROR - NameServer no encontrado: {e}")
            return False
    
    def test_endpoints_servidor(self):
        """Probar endpoints del servidor"""
        print("4. PROBANDO ENDPOINTS DEL SERVIDOR...")
        
        endpoints = [
            ("/health", "GET"),
            ("/nodos/estado", "GET"),
            ("/nodos/disponible", "GET")
        ]
        
        exitos = 0
        for endpoint, metodo in endpoints:
            try:
                if metodo == "GET":
                    response = requests.get(f"{BASE_URL}{endpoint}", headers=self.headers)
                else:
                    response = requests.post(f"{BASE_URL}{endpoint}", headers=self.headers)
                
                if response.status_code == 200:
                    print(f"   OK - {metodo} {endpoint}")
                    exitos += 1
                else:
                    print(f"   ERROR - {metodo} {endpoint}: {response.status_code}")
                    
            except Exception as e:
                print(f"   ERROR - {metodo} {endpoint}: {e}")
        
        return exitos == len(endpoints)
    
    def test_procesamiento_completo(self):
        """Probar procesamiento completo a través del servidor"""
        print("5. PROBANDO PROCESAMIENTO COMPLETO...")
        
        try: 
            img = Image.new('RGB', (200, 200), color='purple')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            files = {
                'files': ('test_image.png', img_bytes, 'image/png')
            }
            
            data = {
                'transformaciones': '''[
                    {"tipo": "escala_grises", "parametros": {}},
                    {"tipo": "redimensionar", "parametros": {"ancho": 100, "alto": 100}},
                    {"tipo": "rotar", "parametros": {"grados": 90}}
                ]'''
            }
            
            response = requests.post(
                f"{BASE_URL}/lotes/procesar",
                files=files,
                data=data,
                headers=self.headers
            )
            
            if response.status_code == 200:
                resultado = response.json()
                print("   OK - Procesamiento iniciado correctamente")
                print(f"     - ID: {resultado.get('id_solicitud')}")
                print(f"     - Estado: {resultado.get('estado')}")
                return True
            else:
                print(f"   ERROR - Procesamiento falló: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ERROR - Error en procesamiento: {e}")
            return False
    
    def limpiar(self):
        """Limpiar recursos"""
        print("6. LIMPIANDO RECURSOS...")
        if self.worker_process:
            try:
                self.worker_process.terminate()
                self.worker_process.wait(timeout=5)
                print("   OK - Nodo worker detenido")
            except:
                print("   AVISO - No se pudo detener el nodo worker correctamente")
                self.worker_process.kill()
    
    def ejecutar_pruebas(self):
        """Ejecutar todas las pruebas"""
        print("SISTEMA DISTRIBUIDO - PRUEBAS UNIFICADAS")
        print("=" * 50)
         
        if not self.verificar_rutas():
            print("ERROR: Rutas del sistema incorrectas")
            return False
        
        print()
        
        pasos = [
            self.login,
            self.verificar_nameserver,
            self.iniciar_nodo_worker,
            self.test_endpoints_servidor,
            self.test_procesamiento_completo
        ]
        
        exitos = 0
        total = len(pasos)
        
        for paso in pasos:
            if paso():
                exitos += 1
            print()
        
        self.limpiar()
        
        print("=" * 50)
        print(f"RESULTADO: {exitos}/{total} pruebas exitosas")
        
        if exitos == total:
            print("SISTEMA FUNCIONANDO CORRECTAMENTE!")
        else:
            print("HAY PROBLEMAS QUE NECESITAN ATENCIÓN")
        
        return exitos == total

if __name__ == "__main__":
 
    if len(sys.argv) > 1:
        RUTA_NODOS = sys.argv[1]
        print(f"Usando ruta personalizada: {RUTA_NODOS}")
    
    tester = TestSistemaUnificado()
    exito = tester.ejecutar_pruebas()
    sys.exit(0 if exito else 1)