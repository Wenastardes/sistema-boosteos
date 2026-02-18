import mysql.connector
import hashlib
import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'database': os.environ.get('DB_NAME'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'port': int(os.environ.get('DB_PORT', '15658')),
    'ssl_disabled': False
}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

print("Iniciando creación de tablas...")
conexion = mysql.connector.connect(**DB_CONFIG)
cursor = conexion.cursor()

# Crear tabla usuarios
cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(64) NOT NULL,
        nombre_completo VARCHAR(100) NOT NULL,
        es_admin BOOLEAN DEFAULT FALSE
    )
''')

# Crear tabla boosteos
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

# Crear usuario admin
cursor.execute("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = 'admin'")
if cursor.fetchone()[0] == 0:
    admin_hash = hash_password('admin123')
    cursor.execute(
        "INSERT INTO usuarios (nombre_usuario, password_hash, nombre_completo, es_admin) VALUES (%s, %s, %s, %s)",
        ('admin', admin_hash, 'Administrador', True)
    )
    print("Usuario admin creado")

conexion.commit()
cursor.close()
conexion.close()
print("Base de datos lista")
```

5. Haz clic en **"Commit changes"**

---

### **2. Modificar el Procfile**

1. En tu repositorio de GitHub, haz clic en el archivo **`Procfile`**
2. Haz clic en el **ícono del lápiz** (Edit)
3. Cambia de:
```
web: gunicorn app:app
```

A:
```
web: python init_db.py && gunicorn app:app
```

4. Haz clic en **"Commit changes"**

---

### **3. Esperar el redeploy**

1. Railway detectará los cambios automáticamente
2. Hará un nuevo deploy (verás la actividad en Railway)
3. **Espera 2-3 minutos** a que termine

---

### **4. Regresar el Procfile a la normalidad**

Una vez que termine el deploy:

1. Ve de nuevo al **`Procfile`** en GitHub
2. Edítalo y cámbialo de vuelta a:
```
web: gunicorn app:app
