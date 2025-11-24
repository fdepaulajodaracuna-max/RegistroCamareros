from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'  # Cambia esto
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trevian.db'
db = SQLAlchemy(app)

# ----------------- MODELOS -----------------
class Camarero(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)

class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camarero_id = db.Column(db.Integer, db.ForeignKey('camarero.id'))
    fecha = db.Column(db.Date, nullable=False)
    entrada = db.Column(db.String(5), nullable=False)  # HH:MM
    salida = db.Column(db.String(5), nullable=False)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))

# ----------------- FUNCIONES -----------------
def notificar_twilio(nombre, entrada, salida):
    account_sid = os.environ.get('TWILIO_SID')
    auth_token = os.environ.get('TWILIO_AUTH')
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        from_='whatsapp:+14155238886',
        body=f'{nombre} registró entrada: {entrada}, salida: {salida}',
        to='whatsapp:+34TU_NUMERO'  # Cambia a tu número
    )
    print("Notificación enviada:", message.sid)

# ----------------- RUTAS -----------------
@app.route('/')
def index():
    return redirect(url_for('registrar'))

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nombre = request.form['nombre']
        entrada = request.form['entrada']
        salida = request.form['salida']

        # Validar formato
        try:
            datetime.strptime(entrada, '%H:%M')
            datetime.strptime(salida, '%H:%M')
        except ValueError:
            flash('Formato de hora incorrecto. Usa HH:MM')
            return redirect(url_for('registrar'))

        camarero = Camarero.query.filter_by(nombre=nombre).first()
        if not camarero:
            flash('Camarero no registrado')
            return redirect(url_for('registrar'))

        hoy = datetime.now().date()
        registro_existente = Registro.query.filter_by(camarero_id=camarero.id, fecha=hoy).first()
        if registro_existente:
            flash('Ya has registrado hoy')
            return redirect(url_for('registrar'))

        registro = Registro(camarero_id=camarero.id, fecha=hoy, entrada=entrada, salida=salida)
        db.session.add(registro)
        db.session.commit()

        try:
            notificar_twilio(camarero.nombre, entrada, salida)
        except Exception as e:
            print(f"Error notificando: {e}")

        flash('Registro guardado correctamente')
        return redirect(url_for('registrar'))

    return render_template('registrar.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        nombre = request.form['nombre']
        password = request.form['password']
        admin = Admin.query.filter_by(nombre=nombre, password=password).first()
        if admin:
            session['admin'] = True
            return redirect(url_for('panel_admin'))
        else:
            flash('Usuario o contraseña incorrectos')
    return render_template('login_admin.html')

@app.route('/admin/panel')
def panel_admin():
    if not session.get('admin'):
        flash('Acceso denegado')
        return redirect(url_for('admin_login'))

    camareros = Camarero.query.all()
    registros = Registr
