from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
import hashlib
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_muy_segura_12345'  # Cambia esto por una clave segura
app.permanent_session_lifetime = timedelta(hours=2)  # Sesión dura 2 horas

# ============================================================================
# CONFIGURACIÓN DE BASE DE DATOS MySQL - AIVEN
# ============================================================================
import os

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'mysql-3a8737ea-sistemaboosteos.k.aivencloud.com'),
    'database': os.environ.get('DB_NAME', 'defaultdb'),
    'user': os.environ.get('DB_USER', 'avnadmin'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'port': int(os.environ.get('DB_PORT', '15658')),
    'ssl_disabled': False
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
    """Página de inicio"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
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
    """Cerrar sesión"""
    session.clear()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('login'))

# ============================================================================
# RUTAS PRINCIPALES
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal"""
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return render_template('dashboard.html', stats={})
    
    cursor = conexion.cursor(dictionary=True)
    
    try:
        # Estadísticas del usuario actual
        cursor.execute('''
            SELECT COUNT(*) as total, COALESCE(SUM(precio), 0) as total_ganado
            FROM boosteos
            WHERE usuario_id = %s
        ''', (session['user_id'],))
        mis_stats = cursor.fetchone()
        
        # Estadísticas generales (solo si es admin)
        stats_generales = None
        if session.get('es_admin'):
            cursor.execute('''
                SELECT COUNT(*) as total_boosteos, COALESCE(SUM(precio), 0) as total_general
                FROM boosteos
            ''')
            stats_generales = cursor.fetchone()
            
            cursor.execute('''
                SELECT u.nombre_completo, COUNT(b.id) as total, COALESCE(SUM(b.precio), 0) as ganado
                FROM usuarios u
                LEFT JOIN boosteos b ON u.id = b.usuario_id
                WHERE u.es_admin = FALSE
                GROUP BY u.id, u.nombre_completo
            ''')
            usuarios_stats = cursor.fetchall()
        else:
            usuarios_stats = []
        
        return render_template('dashboard.html', 
                             mis_stats=mis_stats,
                             stats_generales=stats_generales,
                             usuarios_stats=usuarios_stats)
    except Error as e:
        flash(f'Error al cargar estadísticas: {e}', 'error')
        return render_template('dashboard.html', stats={})
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# RUTAS DE BOOSTEOS
# ============================================================================

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_boosteo():
    """Registrar nuevo boosteo"""
    if request.method == 'POST':
        nombre_cliente = request.form.get('nombre_cliente')
        precio = request.form.get('precio')
        rango_inicio = request.form.get('rango_inicio')
        rango_final = request.form.get('rango_final')
        notas = request.form.get('notas', '')
        
        conexion = crear_conexion()
        if not conexion:
            flash('Error al conectar con la base de datos', 'error')
            return redirect(url_for('registrar_boosteo'))
        
        cursor = conexion.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO boosteos 
                (usuario_id, nombre_cliente, precio, rango_inicio, rango_final, notas)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (session['user_id'], nombre_cliente, precio, rango_inicio, rango_final, notas))
            
            conexion.commit()
            flash('¡Boosteo registrado exitosamente!', 'success')
            return redirect(url_for('mis_boosteos'))
        except Error as e:
            flash(f'Error al registrar boosteo: {e}', 'error')
        finally:
            cursor.close()
            conexion.close()
    
    return render_template('registrar.html')

@app.route('/mis-boosteos')
@login_required
def mis_boosteos():
    """Ver mis boosteos"""
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return render_template('mis_boosteos.html', boosteos=[])
    
    cursor = conexion.cursor(dictionary=True)
    
    try:
        cursor.execute('''
            SELECT id, nombre_cliente, precio, rango_inicio, rango_final, 
                   fecha_registro, notas
            FROM boosteos
            WHERE usuario_id = %s
            ORDER BY fecha_registro DESC
        ''', (session['user_id'],))
        
        boosteos = cursor.fetchall()
        
        # Calcular total
        total = sum(float(b['precio']) for b in boosteos)
        
        return render_template('mis_boosteos.html', boosteos=boosteos, total=total)
    except Error as e:
        flash(f'Error al cargar boosteos: {e}', 'error')
        return render_template('mis_boosteos.html', boosteos=[])
    finally:
        cursor.close()
        conexion.close()

@app.route('/todos-boosteos')
@login_required
def todos_boosteos():
    """Ver todos los boosteos del sistema"""
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return render_template('todos_boosteos.html', boosteos=[])
    
    cursor = conexion.cursor(dictionary=True)
    
    try:
        cursor.execute('''
            SELECT b.id, u.nombre_completo as usuario, b.nombre_cliente, b.precio, 
                   b.rango_inicio, b.rango_final, b.fecha_registro, b.notas
            FROM boosteos b
            JOIN usuarios u ON b.usuario_id = u.id
            ORDER BY b.fecha_registro DESC
        ''')
        
        boosteos = cursor.fetchall()
        
        # Calcular total
        total = sum(float(b['precio']) for b in boosteos)
        
        return render_template('todos_boosteos.html', boosteos=boosteos, total=total)
    except Error as e:
        flash(f'Error al cargar boosteos: {e}', 'error')
        return render_template('todos_boosteos.html', boosteos=[])
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# RUTAS DE ADMINISTRADOR
# ============================================================================

@app.route('/admin/eliminar/<int:boosteo_id>', methods=['POST'])
@admin_required
def eliminar_boosteo(boosteo_id):
    """Eliminar un boosteo (solo admin)"""
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return redirect(url_for('todos_boosteos'))
    
    cursor = conexion.cursor()
    
    try:
        cursor.execute("DELETE FROM boosteos WHERE id = %s", (boosteo_id,))
        conexion.commit()
        flash('Boosteo eliminado exitosamente', 'success')
    except Error as e:
        flash(f'Error al eliminar boosteo: {e}', 'error')
    finally:
        cursor.close()
        conexion.close()
    
    return redirect(url_for('todos_boosteos'))

@app.route('/admin/cambiar-contrasena', methods=['GET', 'POST'])
@login_required
def cambiar_contrasena():
    """Cambiar contraseña"""
    if request.method == 'POST':
        password_actual = request.form.get('password_actual')
        nueva_password = request.form.get('nueva_password')
        confirmar_password = request.form.get('confirmar_password')
        
        # Verificar contraseña actual
        usuario = verificar_login(session['username'], password_actual)
        if not usuario:
            flash('Contraseña actual incorrecta', 'error')
            return redirect(url_for('cambiar_contrasena'))
        
        # Verificar que las nuevas contraseñas coincidan
        if nueva_password != confirmar_password:
            flash('Las contraseñas nuevas no coinciden', 'error')
            return redirect(url_for('cambiar_contrasena'))
        
        # Actualizar contraseña
        conexion = crear_conexion()
        if not conexion:
            flash('Error al conectar con la base de datos', 'error')
            return redirect(url_for('cambiar_contrasena'))
        
        cursor = conexion.cursor()
        
        try:
            nuevo_hash = hash_password(nueva_password)
            cursor.execute(
                "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                (nuevo_hash, session['user_id'])
            )
            conexion.commit()
            flash('Contraseña cambiada exitosamente', 'success')
            return redirect(url_for('dashboard'))
        except Error as e:
            flash(f'Error al cambiar contraseña: {e}', 'error')
        finally:
            cursor.close()
            conexion.close()
    
    return render_template('cambiar_contrasena.html')

# ============================================================================
# INICIAR APLICACIÓN
# ============================================================================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
