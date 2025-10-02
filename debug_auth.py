import os
import requests

def verificar_archivos_nodos():
    print("=== VERIFICACIÓN DE ARCHIVOS DE NODOS ===")
    
    archivos_necesarios = [
        'services/gestor_nodos.py',
        'routes/nodo_routes.py', 
        'models/nodo.py',
        'nodo_worker.py',
        'procesador_imagen.py'
    ]
    
    for archivo in archivos_necesarios:
        if os.path.exists(archivo):
            print(f"✅ {archivo}")
        else:
            print(f"❌ {archivo} - NO ENCONTRADO")
    
    # Verificar transformaciones
    print("\n=== TRANSFORMACIONES ===")
    transformaciones_dir = 'transformaciones'
    if os.path.exists(transformaciones_dir):
        archivos_transform = os.listdir(transformaciones_dir)
        for archivo in archivos_transform:
            if archivo.endswith('.py'):
                print(f"✅ transformaciones/{archivo}")
    else:
        print("❌ Directorio 'transformaciones' no encontrado")

def test_endpoints_nodos():
    print("\n=== TEST ENDPOINTS NODOS ===")
    BASE_URL = "http://localhost:8080"
    
    # 1. Login primero
    print("1. Obteniendo token...")
    login_data = {
        "email": "admin@example.com",
        "password": "Admin123!",
        "tipo": "servidor"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            token = response.json()['access_token']
            headers = {"Authorization": f"Bearer {token}"}
            print("   ✅ Token obtenido")
        else:
            print(f"   ❌ Error en login: {response.text}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # 2. Probar endpoints de nodos
    endpoints = [
        ("/nodos/registrar", "POST"),
        ("/nodos/estado", "GET"), 
        ("/nodos/disponible", "GET")
    ]
    
    for endpoint, method in endpoints:
        print(f"\n2. Probando {method} {endpoint}...")
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            else:
                # Para POST, enviar datos de prueba
                test_data = {
                    "ip": "localhost",
                    "descripcion": "Nodo de prueba",
                    "capacidad_total": 10
                }
                response = requests.post(f"{BASE_URL}{endpoint}", json=test_data, headers=headers)
            
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ EXITOSO: {response.json()}")
            else:
                print(f"   ❌ ERROR: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

if __name__ == "__main__":
    verificar_archivos_nodos()
    test_endpoints_nodos()