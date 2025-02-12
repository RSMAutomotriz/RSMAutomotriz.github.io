from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from config import Config
import os

# Importar db de models
from models import db, User, Auto, Servicio, Imagen

app = Flask(__name__)
app.config.from_object(Config)

# Inicializar db con la app
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Credenciales inválidas')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if request.form['password'] != request.form['confirm_password']:
            flash('Las contraseñas no coinciden')
            return redirect(url_for('register'))
        
        user = User(
            nombre=request.form['nombre'],
            apellido=request.form['apellido'],
            email=request.form['email']
        )
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/ingresar_auto', methods=['GET', 'POST'])
@login_required
def ingresar_auto():
    if request.method == 'POST':
        auto = Auto(
            propietario=request.form['propietario'],
            matricula=request.form['matricula'],
            marca=request.form['marca'],
            modelo=request.form['modelo'],
            año=request.form['año'],
            motor_cc=request.form['motor_cc'],
            admitido_por=f"{current_user.nombre} {current_user.apellido}"
        )
        servicio = Servicio(
            kilometraje=request.form['kilometraje'],
            trabajo_realizado=request.form['trabajo_realizado']
        )
        db.session.add(auto)
        db.session.commit()
        servicio.auto_id = auto.id
        db.session.add(servicio)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('ingresar_auto.html')

@app.route('/buscar', methods=['GET'])
@login_required
def buscar():
    return render_template('buscar.html')

@app.route('/buscar_auto', methods=['GET'])
@login_required
def buscar_auto():
    matricula = request.args.get('matricula')
    auto = Auto.query.filter_by(matricula=matricula).first()
    if auto:
        servicios = Servicio.query.filter_by(auto_id=auto.id).all()
        return render_template('resultado_busqueda.html', auto=auto, servicios=servicios)
    flash('Vehículo no encontrado')
    return redirect(url_for('buscar'))

@app.route('/editar/<int:auto_id>', methods=['GET', 'POST'])
@login_required
def editar(auto_id):
    auto = Auto.query.get_or_404(auto_id)
    if request.method == 'POST':
        auto.propietario = request.form['propietario']
        auto.marca = request.form['marca']
        auto.modelo = request.form['modelo']
        auto.año = request.form['año']
        auto.motor_cc = request.form['motor_cc']
        
        nuevo_servicio = Servicio(
            auto_id=auto.id,
            kilometraje=request.form['kilometraje'],
            trabajo_realizado=request.form['trabajo_realizado']
        )
        db.session.add(nuevo_servicio)
        db.session.commit()
        return redirect(url_for('buscar_auto', matricula=auto.matricula))
    servicios = Servicio.query.filter_by(auto_id=auto.id).all()
    return render_template('editar.html', auto=auto, servicios=servicios)

@app.route('/imagenes/<int:auto_id>', methods=['GET', 'POST'])
@login_required
def imagenes(auto_id):
    auto = Auto.query.get_or_404(auto_id)
    if request.method == 'POST':
        if 'imagen' not in request.files:
            flash('No se seleccionó ningún archivo')
            return redirect(request.url)
        file = request.files['imagen']
        if file.filename == '':
            flash('No se seleccionó ningún archivo')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen = Imagen(auto_id=auto.id, filename=filename)
            db.session.add(imagen)
            db.session.commit()
    imagenes = Imagen.query.filter_by(auto_id=auto.id).all()
    return render_template('imagenes.html', auto=auto, imagenes=imagenes)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Crear tablas si no existen
    with app.app_context():
        db.create_all()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
