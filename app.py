from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime
import re
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'MiyagiBestOsito' 

# ======== Configuración Base de Datos ========

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Crear tablas solo si no existen
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lastname TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS automovil
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                matricula TEXT NOT NULL,
                marca TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER NOT NULL,
                motor TEXT NOT NULL,
                kl TEXT NOT NULL,
                work TEXT NOT NULL,
                date TEXT NOT NULL,
                leader_id INTEGER NOT NULL,
                FOREIGN KEY (leader_id) REFERENCES users (id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS volunteers
                (car_id INTEGER,
                user_id INTEGER,
                FOREIGN KEY (car_id) REFERENCES automovil (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                PRIMARY KEY (car_id, user_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS imagenes_auto
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT NOT NULL,
                ruta_imagen TEXT NOT NULL,
                fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (matricula) REFERENCES automovil (matricula))''')
    
    conn.commit()
    conn.close()

def validate_registration(name, lastname, email, password, confirm_password):
    errors = []
    if len(name) < 2 or len(lastname) < 2:
        errors.append("Nombre y apellido deben tener al menos 2 caracteres")
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        errors.append("Email debe tener un formato válido")
    if password != confirm_password:
        errors.append("Contraseña y confirmación deben ser iguales")
    return errors

# ======== Rutas ========

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        lastname = request.form['lastname']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        errors = validate_registration(name, lastname, email, password, confirm_password)
        
        if not errors:
            try:
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (name, lastname, email, password) VALUES (?, ?, ?, ?)",
                         (name, lastname, email, password))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                errors.append("El email ya está registrado")
        
        for error in errors:
            flash(error)
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Limpiar mensajes flash anteriores al cargar la página
    session.pop('_flashes', None)
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['name'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            flash("Email o contraseña incorrectos")
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Modificamos la consulta para obtener solo las misiones donde el usuario es líder
    c.execute("""
        SELECT m.*, u.name as leader_name 
        FROM automovil m 
        JOIN users u ON m.leader_id = u.id 
        WHERE m.date >= date('now') 
        AND m.leader_id = ?
        ORDER BY m.date ASC
    """, (session['user_id'],))
    automovil = c.fetchall()
    conn.close()
    
    return render_template('dashboard.html', automovil=automovil)

@app.route('/nueva', methods=['GET', 'POST'])
def nueva_mision():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Imprimir los datos recibidos para debug
        print("Datos del formulario:", request.form)
        
        try:
            name = request.form['name']
            matricula = request.form['matricula']  # Asegurarnos que este campo existe
            marca = request.form['marca']
            model = request.form['model']
            year = int(request.form['year'])
            motor = request.form['motor']
            kl = request.form['kl']
            work = request.form['work']
            date = request.form['date']
            
            # Validaciones básicas
            if not all([name, matricula, marca, model, motor, kl, work]):
                flash("Todos los campos son obligatorios")
                return redirect(url_for('nueva_mision'))
            
            if year < 1900 or year > datetime.now().year + 1:
                flash("Año del vehículo inválido")
                return redirect(url_for('nueva_mision'))
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("""
                INSERT INTO automovil (name, matricula, marca, model, year, motor, kl, work, date, leader_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, matricula, marca, model, year, motor, kl, work, date, session['user_id']))
            conn.commit()
            conn.close()
            
            return redirect(url_for('dashboard'))
            
        except KeyError as e:
            flash(f"Falta el campo: {str(e)}")
            return redirect(url_for('nueva_mision'))
        except ValueError:
            flash("Formato de fecha o año inválido")
            return redirect(url_for('nueva_mision'))
        except Exception as e:
            flash(f"Error: {str(e)}")
            return redirect(url_for('nueva_mision'))
    
    return render_template('nuevo_auto.html', today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/mision/<int:id>')
def ver_mision(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # En lugar de mostrar el mensaje de error, redirigimos a la página de búsqueda
    return redirect(url_for('buscar_auto'))

@app.route('/mision/<int:id>/editar', methods=['GET', 'POST'])
def editar_mision(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        try:
            # Obtener los datos básicos del formulario
            name = request.form['name']
            matricula = request.form['matricula']
            marca = request.form['marca']
            model = request.form['model']
            year = int(request.form['year'])
            motor = request.form['motor']
            
            # Obtener las listas de datos de trabajo
            fechas = request.form.getlist('date[]')
            kilometrajes = request.form.getlist('kl[]')
            trabajos = request.form.getlist('work[]')
            
            # Primero, eliminar todos los registros existentes con la misma matrícula
            c.execute("DELETE FROM automovil WHERE matricula = ?", (matricula,))
            
            # Insertar todos los registros como nuevos
            for i in range(len(fechas)):
                c.execute("""
                    INSERT INTO automovil 
                    (name, matricula, marca, model, year, motor, kl, work, date, leader_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, matricula, marca, model, year, motor,
                      kilometrajes[i], trabajos[i], fechas[i], session['user_id']))
            
            conn.commit()
            flash("Vehículo actualizado exitosamente")
            return redirect(url_for('buscar_auto'))
            
        except Exception as e:
            flash(f"Error al actualizar: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
            
    # Para GET request
    c.execute("""
        SELECT m.*, u.name as leader_name 
        FROM automovil m 
        JOIN users u ON m.leader_id = u.id 
        WHERE m.matricula = (
            SELECT matricula FROM automovil WHERE id = ?
        )
        ORDER BY m.date
    """, (id,))
    trabajos = c.fetchall()
    
    if not trabajos:
        conn.close()
        flash("No se encontró el vehículo")
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('editar.html', trabajos=trabajos, auto=trabajos[0])

@app.route('/eliminar_trabajo/<int:trabajo_id>', methods=['POST'])
def eliminar_trabajo(trabajo_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Verificar si el trabajo existe
        c.execute("SELECT matricula FROM automovil WHERE id = ?", (trabajo_id,))
        resultado = c.fetchone()
        
        if not resultado:
            conn.close()
            return jsonify({'success': False, 'message': 'Trabajo no encontrado'})
        
        matricula = resultado[0]
        
        # Contar registros para esta matrícula
        c.execute("SELECT COUNT(*) FROM automovil WHERE matricula = ?", (matricula,))
        count = c.fetchone()[0]
        
        if count > 1:
            c.execute("DELETE FROM automovil WHERE id = ?", (trabajo_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        else:
            conn.close()
            return jsonify({
                'success': False, 
                'message': 'No se puede eliminar el último registro de un vehículo'
            })
        
    except Exception as e:
        print(f"Error al eliminar trabajo: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/mision/<int:id>/voluntarme', methods=['POST'])
def voluntarme(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO volunteers (car_id, user_id) VALUES (?, ?)",
                 (id, session['user_id']))
        conn.commit()
    except sqlite3.IntegrityError:
        flash("Ya eres voluntario en esta misión")
    
    conn.close()
    return redirect(url_for('ver_mision', id=id))

@app.route('/buscar', methods=['GET', 'POST'])
def buscar_auto():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        matricula = request.form['matricula']
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Modificamos la consulta para obtener todos los trabajos del vehículo
        c.execute("""
            SELECT m.*, u.name as leader_name 
            FROM automovil m 
            JOIN users u ON m.leader_id = u.id 
            WHERE m.matricula = ?
            ORDER BY m.date DESC
        """, (matricula,))
        trabajos = c.fetchall()
        
        if trabajos:
            # El primer registro contiene la información más reciente
            auto = trabajos[0]
            return render_template('resultado.html', auto=auto, trabajos=trabajos)
        else:
            flash("No se encontró ningún vehículo con esa matrícula")
            return redirect(url_for('buscar_auto'))
    
    return render_template('buscar.html')

# Configuración para subida de imágenes
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/subir-imagen/<matricula>', methods=['GET', 'POST'])
def subir_imagen(matricula):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        if 'imagen' not in request.files:
            flash('No se seleccionó ningún archivo')
            return redirect(request.url)
            
        file = request.files['imagen']
        if file.filename == '':
            flash('No se seleccionó ningún archivo')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{matricula}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            
            # Crear directorio si no existe
            if not os.path.exists(app.config['UPLOAD_FOLDER']): 
                os.makedirs(app.config['UPLOAD_FOLDER'])
                
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("INSERT INTO imagenes_auto (matricula, ruta_imagen) VALUES (?, ?)",
                     (matricula, filename))
            conn.commit()
            conn.close()
            
            flash('Imagen subida exitosamente')
            return redirect(url_for('ver_imagenes', matricula=matricula))
            
    return render_template('subir_imagen.html', matricula=matricula)

@app.route('/imagenes/<matricula>')
def ver_imagenes(matricula):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
        SELECT ruta_imagen, fecha_subida 
        FROM imagenes_auto 
        WHERE matricula = ? 
        ORDER BY fecha_subida DESC
    """, (matricula,))
    imagenes = c.fetchall()
    conn.close()
    
    # Agrupar imágenes por fecha
    imagenes_por_fecha = {}
    for imagen in imagenes:
        fecha = datetime.strptime(imagen[1], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        if fecha not in imagenes_por_fecha:
            imagenes_por_fecha[fecha] = []
        imagenes_por_fecha[fecha].append(imagen[0])
    
    return render_template('ver_imagenes.html', 
                         imagenes=imagenes_por_fecha, 
                         matricula=matricula)
    
@app.route('/eliminar-imagen/<matricula>/<filename>', methods=['POST'])
def eliminar_imagen(matricula, filename):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    
    try:
        # Ruta completa del archivo
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Eliminar de la base de datos primero
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # Verificar si la imagen existe en la base de datos
        c.execute("SELECT * FROM imagenes_auto WHERE matricula = ? AND ruta_imagen = ?", 
                 (matricula, filename))
        if not c.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Imagen no encontrada en la base de datos'}), 404
        
        # Eliminar el registro de la base de datos
        c.execute("DELETE FROM imagenes_auto WHERE matricula = ? AND ruta_imagen = ?", 
                 (matricula, filename))
        conn.commit()
        conn.close()
        
        # Eliminar el archivo físico si existe
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'success': True, 'message': 'Imagen eliminada correctamente'})
        else:
            return jsonify({'success': False, 'message': 'Archivo no encontrado'}), 404
            
    except Exception as e:
        print(f"Error al eliminar imagen: {str(e)}")  # Para debugging
        return jsonify({'success': False, 'message': f'Error al eliminar la imagen: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)