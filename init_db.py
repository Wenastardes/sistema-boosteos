import sqlite3
import hashlib

DB_NAME = 'database.db'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

try:
    print("=== INICIANDO CREACION DE BASE DE DATOS SQLite ===")
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_usuario TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre_completo TEXT NOT NULL,
            es_admin BOOLEAN DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boosteos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre_cliente TEXT NOT NULL,
            precio REAL NOT NULL,
            rango_inicio TEXT NOT NULL,
            rango_final TEXT NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notas TEXT,
            completado BOOLEAN DEFAULT 0,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')
    
    usuarios_lista = [
        {'u': 'admin', 'p': 'admin123', 'n': 'Administrador', 'a': 1},
        {'u': 'nico', 'p': 'nico123', 'n': 'nico', 'a': 0},
        {'u': 'milcao', 'p': 'milcao123', 'n': 'milcao', 'a': 0},
        {'u': 'pache', 'p': 'pache123', 'n': 'pache', 'a': 0}
    ]
    
    for user in usuarios_lista:
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = ?", (user['u'],))
        if cursor.fetchone()[0] == 0:
            h = hash_password(user['p'])
            cursor.execute(
                "INSERT INTO usuarios (nombre_usuario, password_hash, nombre_completo, es_admin) VALUES (?, ?, ?, ?)",
                (user['u'], h, user['n'], user['a'])
            )
            print(f"✓ Usuario {user['u']} creado exitosamente")
        else:
            print(f"✓ Usuario {user['u']} ya existe")
    
    conexion.commit()
    cursor.close()
    conexion.close()
    print("=== BASE DE DATOS LISTA ===")
    
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()