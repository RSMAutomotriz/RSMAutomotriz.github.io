from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from psycopg2 import Error
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import datetime

load_dotenv()

app = Flask(__name__)
port = int(os.environ.get("PORT", 5000))
app.secret_key = 'MiyagiBestOsito'

def get_db_connection():
    try:
        return psycopg2.connect(os.getenv('DATABASE_URL'))
    except Error as e:
        print(f"Error conectando a PostgreSQL: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn is None:
        return
    
    cur = conn.cursor()
    
    cur.execute('''CREATE TABLE IF NOT EXISTS users
                (id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                lastname TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS automovil
                (id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                matricula TEXT NOT NULL,
                marca TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER NOT NULL,
                motor TEXT NOT NULL,
                kl TEXT NOT NULL,
                work TEXT NOT NULL,
                date TEXT NOT NULL,
                leader_id INTEGER NOT NULL REFERENCES users(id))''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS volunteers
                (car_id INTEGER REFERENCES automovil(id),
                user_id INTEGER REFERENCES users(id),
                PRIMARY KEY (car_id, user_id))''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS imagenes_auto
                (id SERIAL PRIMARY KEY,
                matricula TEXT NOT NULL,
                ruta_imagen TEXT NOT NULL,
                fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

    
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos")
        return render_template('index.html', autos=[])
        
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
    
    return render_template('index.html', autos_lider=autos_lider, autos_voluntario=autos_voluntario)

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
    
    return render_template('dashboard.html', user_name=session.get('user_name'))


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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host="0.0.0.0", port=port)
