from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), nullable=False)
    apellido = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Auto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    propietario = db.Column(db.String(128), nullable=False)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    marca = db.Column(db.String(64), nullable=False)
    modelo = db.Column(db.String(64), nullable=False)
    año = db.Column(db.Integer, nullable=False)
    motor_cc = db.Column(db.Float, nullable=False)
    admitido_por = db.Column(db.String(128), nullable=False)

class Servicio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auto_id = db.Column(db.Integer, db.ForeignKey('auto.id'), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    kilometraje = db.Column(db.Integer, nullable=False)
    trabajo_realizado = db.Column(db.Text, nullable=False)

class Imagen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auto_id = db.Column(db.Integer, db.ForeignKey('auto.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)