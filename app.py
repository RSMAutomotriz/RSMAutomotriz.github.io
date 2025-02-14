# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clave_secreta_rsm_automotriz')

# Configuración de la base de datos para Render (PostgreSQL)
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///rsm_automotriz.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración para subida de archivos
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB máximo para subir archivos

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

# Modelos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    contraseña = db.Column(db.String(200), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    vehiculos = db.relationship('Vehiculo', backref='registrado_por', lazy=True)

class Vehiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    propietario = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    año = db.Column(db.Integer, nullable=False)
    motor = db.Column(db.String(20), nullable=False)
    trabajos = db.relationship('Trabajo', backref='vehiculo', lazy=True, cascade='all, delete-orphan')
    imagenes = db.relationship('Imagen', backref='vehiculo', lazy=True, cascade='all, delete-orphan')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Trabajo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kilometraje = db.Column(db.Integer, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculo.id'), nullable=False)

class Imagen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculo.id'), nullable=False)

@app.before_first_request
def create_tables():
    db.create_all()

@app.route('/')
def inicio():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        contraseña = request.form['contraseña']
        
        if len(nombre) < 3 or len(contraseña) <8:
            flash('El nombre debe tener al menos 3 caracteres y la contraseña al menos 8 caracteres', 'danger')
            return redirect(url_for('registro'))
        
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash('El correo electrónico ya está registrado', 'danger')
            return redirect(url_for('registro'))
        
        hash_contraseña = generate_password_hash(contraseña)
        nuevo_usuario = Usuario(nombre=nombre, email=email, contraseña=hash_contraseña)
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        flash('Registro exitoso, ahora puedes iniciar sesión', 'success')
        return redirect(url_for('inicio'))
    
    return render_template('registro.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    contraseña = request.form['contraseña']
    
    usuario = Usuario.query.filter_by(email=email).first()
    
    if usuario and check_password_hash(usuario.contraseña, contraseña):
        session['usuario_id'] = usuario.id
        session['nombre_usuario'] = usuario.nombre
        return redirect(url_for('dashboard'))
    
    flash('Credenciales inválidas', 'danger')
    return redirect(url_for('inicio'))

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('inicio'))
    return render_template('dashboard.html')

@app.route('/ingresar_vehiculo', methods=['GET', 'POST'])
def ingresar_vehiculo():
    if 'usuario_id' not in session:
        return redirect(url_for('inicio'))
    
    if request.method == 'POST':
        propietario = request.form['propietario']
        matricula = request.form['matricula']
        marca = request.form['marca']
        modelo = request.form['modelo']
        año = request.form['año']
        motor = request.form['motor']
        kilometraje = request.form['kilometraje']
        trabajo_realizado = request.form['trabajo_realizado']
        
        # Verificar si ya existe la matrícula
        vehiculo_existente = Vehiculo.query.filter_by(matricula=matricula).first()
        if vehiculo_existente:
            flash('Ya existe un vehículo con esa matrícula', 'danger')
            return redirect(url_for('ingresar_vehiculo'))
        
        nuevo_vehiculo = Vehiculo(
            propietario=propietario,
            matricula=matricula,
            marca=marca,
            modelo=modelo,
            año=año,
            motor=motor,
            usuario_id=session['usuario_id']
        )
        
        db.session.add(nuevo_vehiculo)
        db.session.commit()
        
        # Agregar el trabajo inicial
        nuevo_trabajo = Trabajo(
            kilometraje=kilometraje,
            descripcion=trabajo_realizado,
            vehiculo_id=nuevo_vehiculo.id
        )
        
        db.session.add(nuevo_trabajo)
        db.session.commit()
        
        flash('Vehículo registrado exitosamente', 'success')
        return redirect(url_for('buscar_vehiculo'))
    
    return render_template('ingresar_vehiculo.html')

@app.route('/buscar_vehiculo', methods=['GET'])
def buscar_vehiculo():
    if 'usuario_id' not in session:
        return redirect(url_for('inicio'))
    return render_template('buscar_vehiculo.html')

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    term = request.args.get('term', '')
    if len(term) <2:
        return jsonify([])
    
    vehiculos = Vehiculo.query.filter(Vehiculo.matricula.ilike(f'%{term}%')).all()
    resultados = [vehiculo.matricula for vehiculo in vehiculos]
    return jsonify(resultados)

@app.route('/ver_vehiculo/<matricula>')
def ver_vehiculo(matricula):
    if 'usuario_id' not in session:
        return redirect(url_for('inicio'))
    
    vehiculo = Vehiculo.query.filter_by(matricula=matricula).first_or_404()
    usuario = Usuario.query.get(vehiculo.usuario_id)
    trabajos = Trabajo.query.filter_by(vehiculo_id=vehiculo.id).order_by(Trabajo.fecha.desc()).all()
    
    return render_template('ver_vehiculo.html', vehiculo=vehiculo, trabajos=trabajos, usuario=usuario)

@app.route('/editar_vehiculo/<matricula>', methods=['GET', 'POST'])
def editar_vehiculo(matricula):
    if 'usuario_id' not in session:
        return redirect(url_for('inicio'))
    
    vehiculo = Vehiculo.query.filter_by(matricula=matricula).first_or_404()
    
    if request.method == 'POST':
        vehiculo.propietario = request.form['propietario']
        vehiculo.marca = request.form['marca']
        vehiculo.modelo = request.form['modelo']
        vehiculo.año = request.form['año']
        vehiculo.motor = request.form['motor']
        
        # Actualizar trabajos existentes
        trabajo_ids = request.form.getlist('trabajo_id')
        kilometrajes = request.form.getlist('kilometraje')
        descripciones = request.form.getlist('descripcion')
        
        for i, trabajo_id in enumerate(trabajo_ids):
            if trabajo_id:  # Actualizar trabajo existente
                trabajo = Trabajo.query.get(trabajo_id)
                if trabajo:
                    trabajo.kilometraje = kilometrajes[i]
                    trabajo.descripcion = descripciones[i]
        
        # Agregar nuevos trabajos
        nuevos_kilometrajes = request.form.getlist('nuevo_kilometraje')
        nuevas_descripciones = request.form.getlist('nueva_descripcion')
        
        for i in range(len(nuevos_kilometrajes)):
            if nuevos_kilometrajes[i] and nuevas_descripciones[i]:
                nuevo_trabajo = Trabajo(
                    kilometraje=nuevos_kilometrajes[i],
                    descripcion=nuevas_descripciones[i],
                    vehiculo_id=vehiculo.id
                )
                db.session.add(nuevo_trabajo)
        
        db.session.commit()
        flash('Vehículo actualizado exitosamente', 'success')
        return redirect(url_for('ver_vehiculo', matricula=vehiculo.matricula))
    
    trabajos = Trabajo.query.filter_by(vehiculo_id=vehiculo.id).order_by(Trabajo.fecha.desc()).all()
    return render_template('editar_vehiculo.html', vehiculo=vehiculo, trabajos=trabajos)

@app.route('/eliminar_trabajo/<int:trabajo_id>', methods=['POST'])
def eliminar_trabajo(trabajo_id):
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'})
    
    trabajo = Trabajo.query.get_or_404(trabajo_id)
    vehiculo = Vehiculo.query.get(trabajo.vehiculo_id)
    
    db.session.delete(trabajo)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/imagenes_vehiculo/<matricula>', methods=['GET'])
def imagenes_vehiculo(matricula):
    if 'usuario_id' not in session:
        return redirect(url_for('inicio'))
    
    vehiculo = Vehiculo.query.filter_by(matricula=matricula).first_or_404()
    imagenes = Imagen.query.filter_by(vehiculo_id=vehiculo.id).order_by(Imagen.fecha_subida.desc()).all()
    
    return render_template('imagenes_vehiculo.html', vehiculo=vehiculo, imagenes=imagenes)

@app.route('/subir_imagen/<matricula>', methods=['GET', 'POST'])
def subir_imagen(matricula):
    if 'usuario_id' not in session:
        return redirect(url_for('inicio'))
    
    if request.method == 'POST':
        vehiculo = Vehiculo.query.filter_by(matricula=matricula).first_or_404()
        
        if 'imagen' not in request.files:
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(url_for('imagenes_vehiculo', matricula=matricula))
        
        archivo = request.files['imagen']
        
        if archivo.filename == '':
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(url_for('imagenes_vehiculo', matricula=matricula))
        
        if archivo:
            nombre_seguro = secure_filename(archivo.filename)
            nombre_archivo = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{nombre_seguro}"
            ruta_completa = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
            archivo.save(ruta_completa)
            
            nueva_imagen = Imagen(
                nombre_archivo=nombre_archivo,
                vehiculo_id=vehiculo.id
            )
            
            db.session.add(nueva_imagen)
            db.session.commit()
            
            flash('Imagen subida exitosamente', 'success')
        
        return redirect(url_for('imagenes_vehiculo', matricula=matricula))
    
    # Si es GET, redirigir a la página de imágenes
    return redirect(url_for('imagenes_vehiculo', matricula=matricula))
@app.route('/eliminar_imagen/<int:imagen_id>', methods=['POST'])
def eliminar_imagen(imagen_id):
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'})
    
    imagen = Imagen.query.get_or_404(imagen_id)
    vehiculo = Vehiculo.query.get(imagen.vehiculo_id)
    
    try:
        ruta_completa = os.path.join(app.config['UPLOAD_FOLDER'], imagen.nombre_archivo)
        if os.path.exists(ruta_completa):
            os.remove(ruta_completa)
        
        db.session.delete(imagen)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/cerrar_sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('inicio'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
