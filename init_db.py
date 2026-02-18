import mysql.connector
import hashlib

# Valores directos (temporalmente)
DB_CONFIG = {
    'host': 'mysql.railway.internal',
    'database': 'railway',
    'user': 'root',
    'password': 'hFGqCVVPOBMdZjUVjHNnbPdXUftu5Rbr',
    'port': 3306
}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

try:
    print("=== INICIANDO CREACION DE BASE DE DATOS ===")
    print(f"Conectando a: {DB_CONFIG['host']}")
    
    conexion = mysql.connector.connect(**DB_CONFIG)
    cursor = conexion.cursor()
    
    print("✓ Conexion exitosa")
    
    # Crear tabla usuarios
    print("Creando tabla usuarios...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(64) NOT NULL,
            nombre_completo VARCHAR(100) NOT NULL,
            es_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    print("✓ Tabla usuarios creada")
    
    # Crear tabla boosteos
    print("Creando tabla boosteos...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boosteos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            nombre_cliente VARCHAR(100) NOT NULL,
            precio DECIMAL(10, 2) NOT NULL,
            rango_inicio VARCHAR(50) NOT NULL,
            rango_final VARCHAR(50) NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notas TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')
    print("✓ Tabla boosteos creada")
    
    # Crear usuario admin
    print("Verificando usuario admin...")
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = 'admin'")
    if cursor.fetchone()[0] == 0:
        print("Creando usuario admin...")
        admin_hash = hash_password('admin123')
        cursor.execute(
            "INSERT INTO usuarios (nombre_usuario, password_hash, nombre_completo, es_admin) VALUES (%s, %s, %s, %s)",
            ('admin', admin_hash, 'Administrador', True)
        )
        print("✓ Usuario admin creado exitosamente")
    else:
        print("✓ Usuario admin ya existe")
    
    conexion.commit()
    cursor.close()
    conexion.close()
    
    print("=== BASE DE DATOS LISTA ===")
    
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
