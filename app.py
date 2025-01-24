from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from psycopg2 import Error
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import datetime

load_dotenv()

app = Flask(__name__, 
    static_folder='../Organizador/static',
    static_url_path='/static'
)
port = int(os.environ.get("PORT", 5000))
app.secret_key = 'MiyagiBestOsito'

def get_db_connection():
    try:
        return psycopg2.connect(os.getenv('DATABASE_URL'))
    except Error as e:
        print(f"Error conectando a PostgreSQL: {e}")
        return None

def get_auto_by_matricula(matricula):
    conn = get_db_connection()
    if conn is None:
        return None
    
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, u.name as recibido_por 
        FROM automovil a 
        JOIN users u ON a.leader_id = u.id 
        WHERE a.matricula = %s""", 
        (matricula,))
    auto = cur.fetchone()
    cur.close()
    conn.close()
    return auto

def get_auto(id):
    conn = get_db_connection()
    if conn is None:
        return None
    
    try:
        cur = conn.cursor()
        # Obtener el auto principal (con leader_id)
        cur.execute("""
            SELECT * FROM automovil 
            WHERE id = %s
            """, (id,))
        auto = cur.fetchone()
        
        cur.close()
        conn.close()
        return auto
    except Exception as e:
        print(f"Error en get_auto: {e}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return None

def get_trabajos(auto_id):
    conn = get_db_connection()
    if conn is None:
        return []
    
    try:
        cur = conn.cursor()
        # Primero obtener la matrícula del auto
        cur.execute("SELECT matricula FROM automovil WHERE id = %s", (auto_id,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return []
        
        matricula = result[0]
        
        # Obtener todos los trabajos para esta matrícula
        cur.execute("""
            SELECT * FROM automovil 
            WHERE matricula = %s 
            ORDER BY date DESC
            """, (matricula,))
        trabajos = cur.fetchall()
        
        cur.close()
        conn.close()
        return trabajos
    except Exception as e:
        print(f"Error en get_trabajos: {e}")
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        return []

def update_auto(id, name, matricula, marca, model, year, motor):
    conn = get_db_connection()
    if conn is None:
        return False
    
    try:
        cur = conn.cursor()
        
        # Actualizar el auto principal
        cur.execute("""
            UPDATE automovil 
            SET name = %s, 
                matricula = %s, 
                marca = %s, 
                model = %s, 
                year = %s, 
                motor = %s 
            WHERE id = %s""", 
            (name, matricula, marca, model, year, motor, id))
        
        # Actualizar la matrícula en los registros de trabajo
        if cur.rowcount > 0:
            cur.execute("""
                UPDATE automovil 
                SET name = %s, 
                    matricula = %s, 
                    marca = %s, 
                    model = %s, 
                    year = %s, 
                    motor = %s 
                WHERE matricula = (
                    SELECT matricula 
                    FROM automovil 
                    WHERE id = %s
                ) AND id != %s""", 
                (name, matricula, marca, model, year, motor, id, id))
            
            conn.commit()
            cur.close()
            conn.close()
            return True
        else:
            print("No se encontró el auto para actualizar")
            conn.rollback()
            cur.close()
            conn.close()
            return False
        
    except Exception as e:
        print(f"Error en update_auto: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return False

def update_trabajos(auto_id, dates, kls, works):
    conn = get_db_connection()
    if conn is None:
        return False
    
    try:
        cur = conn.cursor()
        
        # Obtener los datos existentes del auto principal
        cur.execute("""
            SELECT name, matricula, marca, model, year, motor, leader_id 
            FROM automovil 
            WHERE id = %s""", 
            (auto_id,))
        auto_data = cur.fetchone()
        
        if not auto_data:
            print("No se encontró el auto principal")
            return False
        
        # Eliminar los trabajos existentes para este auto
        cur.execute("""
            DELETE FROM automovil 
            WHERE matricula = %s AND leader_id IS NULL""", 
            (auto_data[1],))
        
        # Insertar los trabajos actualizados
        for date, kl, work in zip(dates, kls, works):
            if work.strip():  # Solo insertar si hay trabajo
                cur.execute("""
                    INSERT INTO automovil 
                    (name, matricula, marca, model, year, motor, kl, work, date, leader_id) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                    """, 
                    (auto_data[0], auto_data[1], auto_data[2], auto_data[3], 
                     auto_data[4], auto_data[5], kl, work, date))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error en update_trabajos: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return False

def delete_trabajo(trabajo_id):
    conn = get_db_connection()
    if conn is None:
        return False
    
    cur = conn.cursor()
    cur.execute("DELETE FROM automovil WHERE id = %s", (trabajo_id,))
    conn.commit()
    cur.close()
    conn.close()
    return True

def init_db():
    conn = get_db_connection()
    if conn is None:
        return
    
    cur = conn.cursor()
    
    # Primero verificar si la columna matricula ya tiene la restricción única
    cur.execute("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'automovil' 
        AND constraint_type = 'UNIQUE'
        AND constraint_name = 'unique_matricula'
    """)
    
    if not cur.fetchone():
        # Si no existe la restricción única, la agregamos
        try:
            cur.execute('''
                ALTER TABLE automovil 
                ADD CONSTRAINT unique_matricula UNIQUE (matricula)
            ''')
            conn.commit()
        except Exception as e:
            print(f"Error al agregar restricción única: {e}")
            conn.rollback()
    
    # Crear la tabla images si no existe
    cur.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            matricula VARCHAR(20) NOT NULL,
            filename VARCHAR(255) NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Intentar agregar la llave foránea si no existe
    cur.execute("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'images' 
        AND constraint_type = 'FOREIGN KEY'
        AND constraint_name = 'fk_matricula'
    """)
    
    if not cur.fetchone():
        try:
            cur.execute('''
                ALTER TABLE images 
                ADD CONSTRAINT fk_matricula 
                FOREIGN KEY (matricula) 
                REFERENCES automovil(matricula) 
                ON DELETE CASCADE
            ''')
            conn.commit()
        except Exception as e:
            print(f"Error al agregar llave foránea: {e}")
            conn.rollback()
    
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

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
                conn = get_db_connection()
                if conn is None:
                    flash("Error de conexión a la base de datos")
                    return render_template('register.html')
                    
                cur = conn.cursor()
                cur.execute("INSERT INTO users (name, lastname, email, password) VALUES (%s, %s, %s, %s)",
                         (name, lastname, email, password))
                conn.commit()
                cur.close()
                conn.close()
                return redirect(url_for('login'))
            except psycopg2.IntegrityError:
                errors.append("El email ya está registrado")
        
        for error in errors:
            flash(error)
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn is None:
            flash("Error de conexión a la base de datos")
            return render_template('login.html')
            
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]  # Aquí guardas el nombre
            return redirect(url_for('dashboard'))  # Redirige al dashboard
        else:
            flash('Email o contraseña incorrectos')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos")
        return render_template('dashboard.html', autos_lider=[], autos_voluntario=[])
        
    cur = conn.cursor()
    
    # Obtener autos donde el usuario es líder
    cur.execute("""
        SELECT a.*, COUNT(v.user_id) as volunteer_count 
        FROM automovil a 
        LEFT JOIN volunteers v ON a.id = v.car_id 
        WHERE a.leader_id = %s 
        GROUP BY a.id
        ORDER BY a.date DESC""", 
        (session['user_id'],))
    autos_lider = cur.fetchall()
    
    # Obtener autos donde el usuario es voluntario
    cur.execute("""
        SELECT a.*, COUNT(v2.user_id) as volunteer_count 
        FROM automovil a 
        INNER JOIN volunteers v1 ON a.id = v1.car_id 
        LEFT JOIN volunteers v2 ON a.id = v2.car_id 
        WHERE v1.user_id = %s 
        GROUP BY a.id
        ORDER BY a.date DESC""", 
        (session['user_id'],))
    autos_voluntario = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', autos_lider=autos_lider, autos_voluntario=autos_voluntario)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create_auto', methods=['GET', 'POST'])
def create_auto():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        matricula = request.form['matricula']
        marca = request.form['marca']
        model = request.form['model']
        year = request.form['year']
        motor = request.form['motor']
        kl = request.form['kl']
        work = request.form['work']
        date = request.form['date']
        
        conn = get_db_connection()
        if conn is None:
            flash("Error de conexión a la base de datos")
            return render_template('create_auto.html')
            
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO automovil (name, matricula, marca, model, year, motor, kl, work, date, leader_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id""",
            (name, matricula, marca, model, year, motor, kl, work, date, session['user_id']))
        
        auto_id = cur.fetchone()[0]
        
        # Procesar imágenes
        if 'images' in request.files:
            images = request.files.getlist('images')
            for image in images:
                if image and allowed_file(image.filename):
                    filename = secure_filename(image.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image.save(filepath)
                    
                    cur.execute("""
                        INSERT INTO imagenes_auto (matricula, ruta_imagen)
                        VALUES (%s, %s)""",
                        (matricula, filename))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return redirect(url_for('index'))
    
    return render_template('create_auto.html')

@app.route('/auto/<int:auto_id>')
def view_auto(auto_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos")
        return redirect(url_for('index'))
        
    cur = conn.cursor()
    
    # Obtener detalles del auto
    cur.execute("""
        SELECT a.*, u.name as leader_name, u.lastname as leader_lastname 
        FROM automovil a 
        JOIN users u ON a.leader_id = u.id 
        WHERE a.id = %s""", 
        (auto_id,))
    auto = cur.fetchone()
    
    if not auto:
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    
    # Obtener voluntarios
    cur.execute("""
        SELECT u.id, u.name, u.lastname 
        FROM users u 
        JOIN volunteers v ON u.id = v.user_id 
        WHERE v.car_id = %s""", 
        (auto_id,))
    volunteers = cur.fetchall()
    
    # Obtener imágenes
    cur.execute("SELECT ruta_imagen FROM imagenes_auto WHERE matricula = %s", (auto[2],))
    images = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('view_auto.html', auto=auto, volunteers=volunteers, images=images)

@app.route('/join/<int:auto_id>')
def join_auto(auto_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos")
        return redirect(url_for('index'))
        
    cur = conn.cursor()
    
    try:
        cur.execute("INSERT INTO volunteers (car_id, user_id) VALUES (%s, %s)",
                   (auto_id, session['user_id']))
        conn.commit()
    except psycopg2.IntegrityError:
        flash('Ya eres voluntario en este auto')
    
    cur.close()
    conn.close()
    
    return redirect(url_for('view_auto', auto_id=auto_id))

@app.route('/leave/<int:auto_id>')
def leave_auto(auto_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos")
        return redirect(url_for('index'))
        
    cur = conn.cursor()
    cur.execute("DELETE FROM volunteers WHERE car_id = %s AND user_id = %s",
               (auto_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    
    return redirect(url_for('view_auto', auto_id=auto_id))

def validate_registration(name, lastname, email, password, confirm_password):
    errors = []
    if not name or not lastname or not email or not password:
        errors.append("Todos los campos son obligatorios")
    if password != confirm_password:
        errors.append("Las contraseñas no coinciden")
    if len(password) < 6:
        errors.append("La contraseña debe tener al menos 6 caracteres")
    return errors

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/buscar', methods=['GET', 'POST'])
def buscar_auto():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        matricula = request.form.get('matricula', '')
        
        conn = get_db_connection()
        if conn is None:
            flash('Error de conexión a la base de datos')
            return render_template('buscar.html')
        
        try:
            cur = conn.cursor()
            # Buscar el auto principal
            cur.execute("""
                SELECT * FROM automovil 
                WHERE matricula = %s
                ORDER BY id ASC
                LIMIT 1
                """, (matricula,))
            auto = cur.fetchone()
            
            if auto:
                # Obtener todos los trabajos relacionados
                cur.execute("""
                    SELECT * FROM automovil 
                    WHERE matricula = %s 
                    ORDER BY date DESC
                    """, (matricula,))
                trabajos = cur.fetchall()
                
                return render_template('resultado.html', auto=auto, trabajos=trabajos)
            else:
                flash('No se encontró ningún vehículo con esa matrícula')
        
        except Exception as e:
            print(f"Error en buscar_auto: {e}")
            flash('Error al buscar el vehículo')
        
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    
    return render_template('buscar.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_mision(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            matricula = request.form.get('matricula')
            marca = request.form.get('marca')
            model = request.form.get('model')
            year = request.form.get('year')
            motor = request.form.get('motor')
            
            dates = request.form.getlist('date[]')
            kls = request.form.getlist('kl[]')
            works = request.form.getlist('work[]')
            
            conn = get_db_connection()
            if conn is None:
                flash('Error de conexión a la base de datos')
                return redirect(url_for('buscar_auto'))
            
            cur = conn.cursor()
            
            # Actualizar el auto principal
            cur.execute("""
                UPDATE automovil 
                SET name = %s, 
                    matricula = %s, 
                    marca = %s, 
                    model = %s, 
                    year = %s, 
                    motor = %s 
                WHERE id = %s
                """, (name, matricula, marca, model, year, motor, id))
            
            # Actualizar o insertar trabajos
            for date, kl, work in zip(dates, kls, works):
                if work.strip():  # Solo procesar si hay trabajo
                    cur.execute("""
                        INSERT INTO automovil 
                        (name, matricula, marca, model, year, motor, kl, work, date) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE 
                        SET kl = EXCLUDED.kl,
                            work = EXCLUDED.work,
                            date = EXCLUDED.date
                        """, 
                        (name, matricula, marca, model, year, motor, kl, work, date))
            
            conn.commit()
            flash('Vehículo actualizado exitosamente')
            return redirect(url_for('buscar_auto'))
            
        except Exception as e:
            print(f"Error en editar_mision: {e}")
            flash('Error al actualizar el vehículo')
            if 'conn' in locals():
                conn.rollback()
            
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
    
    # GET request
    auto = get_auto(id)
    if not auto:
        flash('Vehículo no encontrado')
        return redirect(url_for('buscar_auto'))
    
    trabajos = get_trabajos(id)
    print(f"Auto encontrado: {auto}")
    print(f"Trabajos encontrados: {len(trabajos)}")
    
    return render_template('editar.html', 
                         auto=auto, 
                         trabajos=trabajos,
                         today=datetime.datetime.now().strftime('%Y-%m-%d'))

@app.route('/eliminar_trabajo/<int:trabajo_id>', methods=['POST'])
def eliminar_trabajo(trabajo_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'})
        
    try:
        if delete_trabajo(trabajo_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Error al eliminar el trabajo'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/ver_imagenes/<matricula>')
def ver_imagenes(matricula):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Obtener imágenes organizadas por fecha
    imagenes = get_images_by_matricula(matricula)
    return render_template('ver_imagenes.html', matricula=matricula, imagenes=imagenes)

@app.route('/subir_imagen/<matricula>', methods=['GET', 'POST'])
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
            filename = secure_filename(f"{matricula}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            save_image_to_db(matricula, filename)
            flash('Imagen subida exitosamente')
            return redirect(url_for('ver_imagenes', matricula=matricula))
            
    return render_template('subir_imagen.html', matricula=matricula)

@app.route('/eliminar-imagen/<matricula>/<filename>', methods=['POST'])
def eliminar_imagen(matricula, filename):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'})
    
    try:
        # Eliminar archivo físico
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Eliminar registro de la base de datos
        delete_image_from_db(matricula, filename)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Funciones auxiliares para manejar imágenes
def get_images_by_matricula(matricula):
    conn = get_db_connection()
    if conn is None:
        return {}
    
    cur = conn.cursor()
    cur.execute("""
        SELECT filename, upload_date 
        FROM images 
        WHERE matricula = %s 
        ORDER BY upload_date DESC""", 
        (matricula,))
    
    images = cur.fetchall()
    cur.close()
    conn.close()
    
    # Organizar imágenes por fecha
    imagenes_por_fecha = {}
    for img in images:
        fecha = img[1].strftime('%Y-%m-%d')
        if fecha not in imagenes_por_fecha:
            imagenes_por_fecha[fecha] = []
        imagenes_por_fecha[fecha].append(img[0])
    
    return imagenes_por_fecha

def save_image_to_db(matricula, filename):
    conn = get_db_connection()
    if conn is None:
        return False
    
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO images (matricula, filename, upload_date) 
        VALUES (%s, %s, NOW())""", 
        (matricula, filename))
    conn.commit()
    cur.close()
    conn.close()
    return True

def delete_image_from_db(matricula, filename):
    conn = get_db_connection()
    if conn is None:
        return False
    
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM images 
        WHERE matricula = %s AND filename = %s""", 
        (matricula, filename))
    conn.commit()
    cur.close()
    conn.close()
    return True

# Configuración para subida de archivos
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host="0.0.0.0", port=port)
