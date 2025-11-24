from flask import Flask, request, redirect, render_template, session
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
import os

app = Flask(__name__)
app.secret_key = 'mi_clave_super_segura'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///registro.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# MODELOS
class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    entrada = db.Column(db.String(10), nullable=False)
    salida = db.Column(db.String(10), nullable=False)

# CREAR BASE DE DATOS
with app.app_context():
    db.create_all()

# ADMIN (solo tú)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'paco123'  # cambia esta contraseña si quieres

# TWILIO
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = 'whatsapp:+14155238886'
TWILIO_WHATSAPP_TO = 'whatsapp:+34TU_NUMERO'  # tu número de móvil

def enviar_whatsapp(nombre, entrada, salida):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print(f"{nombre} registró entrada a las {entrada} (Twilio no configurado)")
        return
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    mensaje = f"{nombre} registró entrada: {entrada}, salida: {salida}"
    client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=TWILIO_WHATSAPP_TO,
        body=mensaje
    )

# RUTAS
@app.route('/')
def home():
    return render_template('registro.html')

@app.route('/registrar', methods=['POST'])
def registrar():
    nombre = request.form['nombre']
    entrada = request.form['entrada']
    salida = request.form['salida']

    # Verificar si ya registró hoy
    registro_existente = Registro.query.filter_by(nombre=nombre, entrada=entrada).first()
    if registro_existente:
        return "Ya registraste hoy"

    registro = Registro(nombre=nombre, entrada=entrada, salida=salida)
    db.session.add(registro)
    db.session.commit()

    enviar_whatsapp(nombre, entrada, salida)

    return "Registro guardado"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin')
        else:
            return "Usuario o contraseña incorrecta"
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/login')
    registros = Registro.query.all()
    return render_template('admin.html', registros=registros)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
