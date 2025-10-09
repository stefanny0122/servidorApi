from database import init_db, test_connections
from utils.logger import get_logger

logger = get_logger("DatabaseInit")

def main():
    print("Inicializando base de datos...")
    try: 
        init_db()
        print("Tablas creadas exitosamente")
         
        test_connections()
        print("Conexiones a BD verificadas")
        
        print("Base de datos inicializada correctamente")
        
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")
        logger.error(f"Error inicializando base de datos: {e}")

if __name__ == "__main__":
    main()