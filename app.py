from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import hashlib
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_muy_segura_12345'
app.permanent_session_lifetime = timedelta(hours=2)

DB_NAME = 'database.db'

# ============================================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================================

def crear_conexion():
    """Crea una conexión a la base de datos SQLite"""
    try:
        conexion = sqlite3.connect(DB_NAME)
        conexion.row_factory = sqlite3.Row
        return conexion
    except Exception as e:
        print(f"Error al conectar a SQLite: {e}")
        return None

def hash_password(password):
    """Genera un hash de la contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_login(username, password):
    """Verifica las credenciales del usuario"""
    conexion = crear_conexion()
    if not conexion:
        return None
    
    cursor = conexion.cursor()
    try:
        password_hash = hash_password(password)
        cursor.execute(
            "SELECT id, nombre_usuario, nombre_completo, es_admin FROM usuarios WHERE nombre_usuario = ? AND password_hash = ?",
            (username, password_hash)
        )
        usuario = cursor.fetchone()
        return usuario
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# DECORADORES
# ============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión primero', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
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

@app.route('/cambiar-contrasena', methods=['GET', 'POST'])
@login_required
def cambiar_contrasena():
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
            cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (nuevo_hash, session['user_id']))
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
        return render_template('dashboard.html', mis_stats={}, mis_boosteos_count=0, total_ganado=0.0)
    cursor = conexion.cursor()
    try:
        cursor.execute('''
            SELECT COUNT(*) as total, COALESCE(SUM(precio), 0) as total_ganado
            FROM boosteos WHERE usuario_id = ?
        ''', (session['user_id'],))
        mis_stats = cursor.fetchone()
        
        mis_boosteos_count = mis_stats['total'] if mis_stats else 0
        total_ganado = float(mis_stats['total_ganado']) if mis_stats else 0.0

        stats_generales = None
        usuarios_stats = []
        if session.get('es_admin'):
            cursor.execute('SELECT COUNT(*) as total_boosteos, COALESCE(SUM(precio), 0) as total_general FROM boosteos')
            stats_generales = cursor.fetchone()
            cursor.execute('''
                SELECT u.nombre_completo, COUNT(b.id) as total, COALESCE(SUM(b.precio), 0) as ganado
                FROM usuarios u
                LEFT JOIN boosteos b ON u.id = b.usuario_id
                WHERE u.es_admin = 0 GROUP BY u.id, u.nombre_completo
            ''')
            usuarios_stats = cursor.fetchall()

        return render_template(
            'dashboard.html', 
            mis_stats=mis_stats, 
            mis_boosteos_count=mis_boosteos_count,
            total_ganado=total_ganado,
            stats_generales=stats_generales, 
            usuarios_stats=usuarios_stats
        )
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# RUTAS DE BOOSTEOS
# ============================================================================

@app.route('/registrar', methods=['GET', 'POST'], endpoint='registrar_boosteo')
@app.route('/registrar-boosteo', methods=['GET', 'POST'], endpoint='registrar')
@login_required
def registrar_boosteo():
    if request.method == 'POST':
        nombre_cliente = request.form.get('nombre_cliente')
        precio = request.form.get('precio')
        rango_inicio = request.form.get('rango_inicio')
        rango_final = request.form.get('rango_final')
        notas = request.form.get('notas', '')
        completado = 1 if request.form.get('completado') else 0
        
        conexion = crear_conexion()
        if not conexion: 
            return redirect(url_for('registrar_boosteo'))
        cursor = conexion.cursor()
        try:
            cursor.execute('''
                INSERT INTO boosteos (usuario_id, nombre_cliente, precio, rango_inicio, rango_final, notas, completado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT * FROM boosteos WHERE id = ?", (boosteo_id,))
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
            completado = 1 if request.form.get('completado') else 0
            cursor.execute('''
                UPDATE boosteos 
                SET nombre_cliente=?, precio=?, rango_inicio=?, rango_final=?, notas=?, completado=?
                WHERE id=?
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
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT usuario_id FROM boosteos WHERE id = ?", (boosteo_id,))
        boosteo = cursor.fetchone()
        
        if not boosteo:
            flash('El registro no existe', 'error')
        elif session.get('es_admin') or boosteo['usuario_id'] == session['user_id']:
            cursor.execute("DELETE FROM boosteos WHERE id = ?", (boosteo_id,))
            conexion.commit()
            flash('Registro eliminado correctamente', 'success')
        else:
            flash('No tienes permiso para eliminar este registro', 'error')
            
        return redirect(request.referrer or url_for('mis_boosteos'))
    finally:
        cursor.close()
        conexion.close()

@app.route('/mis-boosteos')
@login_required
def mis_boosteos():
    conexion = crear_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute('SELECT * FROM boosteos WHERE usuario_id = ? ORDER BY fecha_registro DESC', (session['user_id'],))
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
    cursor = conexion.cursor()
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
# SECCIÓN 1: CUENTAS RANKED READY
# ============================================================================

@app.route('/cuentas-ranked-ready', methods=['GET', 'POST'])
@login_required
def cuentas_ranked_ready():
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return redirect(url_for('dashboard'))
    cursor = conexion.cursor()
    try:
        if request.method == 'POST':
            correo_cuenta = request.form.get('correo_cuenta')
            password_cuenta = request.form.get('password_cuenta')
            estado = request.form.get('estado', 'No Usada')
            notas = request.form.get('notas', '')

            cursor.execute('''
                INSERT INTO cuentas_ranked (usuario_cuenta, password_cuenta, nivel, estado, notas)
                VALUES (?, ?, '', ?, ?)
            ''', (correo_cuenta, password_cuenta, estado, notas))
            conexion.commit()
            flash('Cuenta Ranked registrada correctamente', 'success')
            return redirect(url_for('cuentas_ranked_ready'))

        cursor.execute('SELECT * FROM cuentas_ranked ORDER BY fecha_creacion DESC')
        cuentas = cursor.fetchall()
        return render_template('cuentas_ranked_ready.html', cuentas=cuentas)
    finally:
        cursor.close()
        conexion.close()

@app.route('/cuentas-ranked-ready/estado/<int:id>', methods=['POST'])
@login_required
def cambiar_estado_cuenta_ranked(id):
    nuevo_estado = request.form.get('estado')
    conexion = crear_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute("UPDATE cuentas_ranked SET estado = ? WHERE id = ?", (nuevo_estado, id))
        conexion.commit()
        flash(f'Estado actualizado a: {nuevo_estado}', 'success')
        return redirect(url_for('cuentas_ranked_ready'))
    finally:
        cursor.close()
        conexion.close()

@app.route('/cuentas-ranked-ready/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_cuenta_ranked(id):
    conexion = crear_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute("DELETE FROM cuentas_ranked WHERE id = ?", (id,))
        conexion.commit()
        flash('Cuenta eliminada del inventario', 'success')
        return redirect(url_for('cuentas_ranked_ready'))
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# SECCIÓN 2: CORREOS INBOX
# ============================================================================

@app.route('/correos-inbox', methods=['GET', 'POST'])
@login_required
def correos_inbox():
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return redirect(url_for('dashboard'))
    cursor = conexion.cursor()
    try:
        if request.method == 'POST':
            correo = request.form.get('correo')
            password_correo = request.form.get('password_correo')
            proveedor = request.form.get('proveedor', 'inbox.eu')
            notas = request.form.get('notas', '')

            cursor.execute('''
                INSERT INTO correos_inbox (correo, password_correo, proveedor, notas)
                VALUES (?, ?, ?, ?)
            ''', (correo, password_correo, proveedor, notas))
            conexion.commit()
            flash('Correo registrado con éxito', 'success')
            return redirect(url_for('correos_inbox'))

        cursor.execute('SELECT * FROM correos_inbox ORDER BY fecha_registro DESC')
        correos = cursor.fetchall()
        return render_template('correos_inbox.html', correos=correos)
    finally:
        cursor.close()
        conexion.close()

@app.route('/correos-inbox/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_correo_inbox(id):
    conexion = crear_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute("DELETE FROM correos_inbox WHERE id = ?", (id,))
        conexion.commit()
        flash('Correo eliminado del listado', 'success')
        return redirect(url_for('correos_inbox'))
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# SECCIÓN 3: CUENTAS PARA VENDER
# ============================================================================

@app.route('/cuentas-vender', methods=['GET', 'POST'])
@login_required
def cuentas_vender():
    conexion = crear_conexion()
    if not conexion:
        flash('Error al conectar con la base de datos', 'error')
        return redirect(url_for('dashboard'))
    cursor = conexion.cursor()
    try:
        if request.method == 'POST':
            titulo = request.form.get('titulo')
            rango = request.form.get('rango')
            precio = float(request.form.get('precio', 0.0) or 0.0)
            estado = request.form.get('estado', 'En Venta')
            descripcion = request.form.get('descripcion', '')

            cursor.execute('''
                INSERT INTO cuentas_venta (titulo, rango, precio, estado, descripcion)
                VALUES (?, ?, ?, ?, ?)
            ''', (titulo, rango, precio, estado, descripcion))
            conexion.commit()
            flash('Cuenta publicada exitosamente', 'success')
            return redirect(url_for('cuentas_vender'))

        cursor.execute('SELECT * FROM cuentas_venta ORDER BY fecha_publicacion DESC')
        cuentas = cursor.fetchall()
        return render_template('cuentas_vender.html', cuentas=cuentas)
    finally:
        cursor.close()
        conexion.close()

@app.route('/cuentas-vender/estado/<int:id>', methods=['POST'])
@login_required
def cambiar_estado_cuenta_venta(id):
    nuevo_estado = request.form.get('estado')
    conexion = crear_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute("UPDATE cuentas_venta SET estado = ? WHERE id = ?", (nuevo_estado, id))
        conexion.commit()
        flash(f'Estado actualizado a: {nuevo_estado}', 'success')
        return redirect(url_for('cuentas_vender'))
    finally:
        cursor.close()
        conexion.close()

@app.route('/cuentas-vender/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_cuenta_venta(id):
    conexion = crear_conexion()
    cursor = conexion.cursor()
    try:
        cursor.execute("DELETE FROM cuentas_venta WHERE id = ?", (id,))
        conexion.commit()
        flash('Cuenta retirada del catálogo de venta', 'success')
        return redirect(url_for('cuentas_vender'))
    finally:
        cursor.close()
        conexion.close()

# ============================================================================
# INICIALIZACIÓN AUTOMÁTICA AL ARRANCAR
# ============================================================================

def inicializar_base_datos():
    conexion = crear_conexion()
    if not conexion: 
        return
    cursor = conexion.cursor()
    try:
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cuentas_ranked (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_cuenta TEXT NOT NULL,
                password_cuenta TEXT NOT NULL,
                nivel TEXT,
                estado TEXT DEFAULT 'Disponible',
                notas TEXT,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS correos_inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correo TEXT NOT NULL,
                password_correo TEXT NOT NULL,
                proveedor TEXT,
                notas TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cuentas_venta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                rango TEXT NOT NULL,
                precio REAL NOT NULL,
                estado TEXT DEFAULT 'En Venta',
                descripcion TEXT,
                fecha_publicacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                h = hashlib.sha256(user['p'].encode()).hexdigest()
                cursor.execute("INSERT INTO usuarios (nombre_usuario, password_hash, nombre_completo, es_admin) VALUES (?, ?, ?, ?)", (user['u'], h, user['n'], user['a']))
        conexion.commit()
    except Exception as e:
        print(f"Error al inicializar DB: {e}")
    finally:
        cursor.close()
        conexion.close()

# Ejecución al cargar módulo (imprescindible para WSGI / PythonAnywhere)
inicializar_base_datos()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)