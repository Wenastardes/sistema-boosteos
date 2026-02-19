from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
import hashlib
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_muy_segura_12345'  # Cambia esto por una clave segura
app.permanent_session_lifetime = timedelta(hours=2)  # Sesión dura 2 horas

# ============================================================================
# CONFIGURACIÓN DE BASE DE DATOS MySQL - ACTUALIZADA A RAILWAY
# ============================================================================
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'switchback.proxy.rlwy.net'),
    'database': os.environ.get('DB_NAME', 'railway'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'bDuxDRHyGYYUQpSMmGFDYWIOdWwFuZqS'),
    'port': int(os.environ.get('DB_PORT', '11963')),
    'ssl_disabled': True
}

# ============================================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================================

def crear_conexion():
    """Crea una conexión a la base de datos MySQL"""
    try:
        conexion = mysql.connector.connect(**DB_CONFIG)
        return conexion
    except Exception as e:
        print(f"Error al conectar a MySQL: {e}")
        return None

def hash_password(password):
    """Genera un hash de la contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(username, password):
    """Verifica las credenciales del usuario"""
    conexion = crear_conexion()
    if not conexion:
        return None
    
    cursor = conexion.cursor(dictionary=True)
    try:
        password_hash = hash_password(password)
        cursor.execute(
            "SELECT id, nombre_usuario, nombre_completo, es_admin FROM usuarios WHERE nombre_usuario = %s AND password_hash = %s",
            (username, password_hash)
        )
        usuario = cursor.fetchone()
        return usuario
    except Error as e:
        print(f"Error: {e}")
        return None
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# DECORADORES
# ============================================================================

def login_required(f):
    """Decorador para requerir login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión primero', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorador para requerir permisos de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión primero', 'error')
            return redirect(url_for('login'))
        if not session.get('es_admin'):
            flash('No tienes permisos de administrador', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# RUTAS DE AUTENTICACIÓN
# ============================================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        usuario = verificar_login(username, password)
        if usuario:
            session.permanent = True
            session['user_id'] = usuario['id']
            session['username'] = usuario['nombre_usuario']
            session['nombre_completo'] = usuario['nombre_completo']
            session['es_admin'] = bool(usuario['es_admin'])
            flash(f'¡Bienvenido, {usuario["nombre_completo"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('login'))

# ESTA ES LA FUNCIÓN QUE FALTABA Y HACÍA EXPLOTAR RAILWAY
@app.route('/cambiar-contrasena', methods=['GET', 'POST'])
@login_required
def cambiar_contrasena():
    """Ruta para que los usuarios cambien su clave"""
    if request.method == 'POST':
        password_actual = request.form.get('password_actual')
        nueva_password = request.form.get('nueva_password')
        
        usuario = verificar_login(session['username'], password_actual)
        if not usuario:
            flash('Contraseña actual incorrecta', 'error')
            return redirect(url_for('cambiar_contrasena'))
        
        conexion = crear_conexion()
        cursor = conexion.cursor()
        try:
            nuevo_hash = hash_password(nueva_password)
            cursor.execute("UPDATE usuarios SET password_hash = %s WHERE id = %s", (nuevo_hash, session['user_id']))
            conexion.commit()
            flash('Contraseña actualizada correctamente', 'success')
            return redirect(url_for('dashboard'))
        finally:
            cursor.close()
            conexion.close()
    return render_template('cambiar_contrasena.html')

# ============================================================================
# RUTAS PRINCIPALES
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return render_template('dashboard.html', stats={})
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute('''
            SELECT COUNT(*) as total, COALESCE(SUM(precio), 0) as total_ganado
            FROM boosteos WHERE usuario_id = %s
        ''', (session['user_id'],))
        mis_stats = cursor.fetchone()
        stats_generales = None
        if session.get('es_admin'):
            cursor.execute('SELECT COUNT(*) as total_boosteos, COALESCE(SUM(precio), 0) as total_general FROM boosteos')
            stats_generales = cursor.fetchone()
            cursor.execute('''
                SELECT u.nombre_completo, COUNT(b.id) as total, COALESCE(SUM(b.precio), 0) as ganado
                FROM usuarios u
                LEFT JOIN boosteos b ON u.id = b.usuario_id
                WHERE u.es_admin = FALSE GROUP BY u.id, u.nombre_completo
            ''')
            usuarios_stats = cursor.fetchall()
        else:
            usuarios_stats = []
        return render_template('dashboard.html', mis_stats=mis_stats, stats_generales=stats_generales, usuarios_stats=usuarios_stats)
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# RUTAS DE BOOSTEOS (REGISTRAR, EDITAR, ELIMINAR)
# ============================================================================

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_boosteo():
    if request.method == 'POST':
        nombre_cliente = request.form.get('nombre_cliente')
        precio = request.form.get('precio')
        rango_inicio = request.form.get('rango_inicio')
        rango_final = request.form.get('rango_final')
        notas = request.form.get('notas', '')
        completado = request.form.get('completado', 0)
        
        conexion = crear_conexion()
        if not conexion: return redirect(url_for('registrar_boosteo'))
        cursor = conexion.cursor()
        try:
            cursor.execute('''
                INSERT INTO boosteos (usuario_id, nombre_cliente, precio, rango_inicio, rango_final, notas, completado)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (session['user_id'], nombre_cliente, precio, rango_inicio, rango_final, notas, completado))
            conexion.commit()
            flash('¡Boosteo registrado exitosamente!', 'success')
            return redirect(url_for('mis_boosteos'))
        finally:
            cursor.close()
            conexion.close()
    return render_template('registrar.html')

@app.route('/editar/<int:boosteo_id>', methods=['GET', 'POST'])
@login_required
def editar_boosteo(boosteo_id):
    conexion = crear_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM boosteos WHERE id = %s", (boosteo_id,))
        boosteo = cursor.fetchone()
        if not boosteo or (boosteo['usuario_id'] != session['user_id'] and not session.get('es_admin')):
            flash('No tienes permiso para editar este registro', 'error')
            return redirect(url_for('mis_boosteos'))
        if request.method == 'POST':
            nombre_cliente = request.form.get('nombre_cliente')
            precio = request.form.get('precio')
            rango_inicio = request.form.get('rango_inicio')
            rango_final = request.form.get('rango_final')
            notas = request.form.get('notas', '')
            completado = request.form.get('completado', 0)
            cursor.execute('''
                UPDATE boosteos 
                SET nombre_cliente=%s, precio=%s, rango_inicio=%s, rango_final=%s, notas=%s, completado=%s
                WHERE id=%s
            ''', (nombre_cliente, precio, rango_inicio, rango_final, notas, completado, boosteo_id))
            conexion.commit()
            flash('¡Registro actualizado!', 'success')
            return redirect(url_for('mis_boosteos'))
        return render_template('editar.html', boosteo=boosteo)
    finally:
        cursor.close()
        conexion.close()

@app.route('/eliminar/<int:boosteo_id>', methods=['POST'])
@login_required
def eliminar_boosteo(boosteo_id):
    conexion = crear_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT usuario_id FROM boosteos WHERE id = %s", (boosteo_id,))
        boosteo = cursor.fetchone()
        if not boosteo or (boosteo['usuario_id'] != session['user_id'] and not session.get('es_admin')):
            flash('No tienes permiso para eliminar este registro', 'error')
        else:
            cursor.execute("DELETE FROM boosteos WHERE id = %s", (boosteo_id,))
            conexion.commit()
            flash('Registro eliminado correctamente', 'success')
        return redirect(request.referrer or url_for('mis_boosteos'))
    finally:
        cursor.close()
        conexion.close()

@app.route('/mis-boosteos')
@login_required
def mis_boosteos():
    conexion = crear_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM boosteos WHERE usuario_id = %s ORDER BY fecha_registro DESC', (session['user_id'],))
        boosteos = cursor.fetchall()
        total = sum(float(b['precio']) for b in boosteos)
        return render_template('mis_boosteos.html', boosteos=boosteos, total=total)
    finally:
        cursor.close()
        conexion.close()

@app.route('/todos-boosteos')
@login_required
def todos_boosteos():
    conexion = crear_conexion()
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute('''
            SELECT b.*, u.nombre_completo as usuario 
            FROM boosteos b JOIN usuarios u ON b.usuario_id = u.id 
            ORDER BY b.fecha_registro DESC
        ''')
        boosteos = cursor.fetchall()
        total = sum(float(b['precio']) for b in boosteos)
        return render_template('todos_boosteos.html', boosteos=boosteos, total=total)
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# INICIAR APLICACIÓN E INICIALIZACIÓN
# ============================================================================

def inicializar_base_datos():
    try:
        conexion = crear_conexion()
        if not conexion: return
        cursor = conexion.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(64) NOT NULL,
                nombre_completo VARCHAR(100) NOT NULL,
                es_admin BOOLEAN DEFAULT FALSE
            )
        ''')
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
                completado BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')
        usuarios_lista = [
            {'u': 'admin', 'p': 'admin123', 'n': 'Administrador', 'a': True},
            {'u': 'nico', 'p': 'nico123', 'n': 'nico', 'a': False},
            {'u': 'milcao', 'p': 'milcao123', 'n': 'milcao', 'a': False}
        ]
        for user in usuarios_lista:
            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE nombre_usuario = %s", (user['u'],))
            if cursor.fetchone()[0] == 0:
                h = hashlib.sha256(user['p'].encode()).hexdigest()
                cursor.execute("INSERT INTO usuarios (nombre_usuario, password_hash, nombre_completo, es_admin) VALUES (%s, %s, %s, %s)", (user['u'], h, user['n'], user['a']))
        conexion.commit()
    except Exception as e: print(f"Error: {e}")
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()

if __name__ == '__main__':
    inicializar_base_datos()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
