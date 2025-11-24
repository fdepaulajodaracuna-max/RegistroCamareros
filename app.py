from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from twilio.rest import Client
import os
from datetime import date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Correo
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

db = SQLAlchemy(app)
mail = Mail(app)

# Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM')
WHATSAPP_TO = os.getenv('WHATSAPP_TO')

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    entrada = db.Column(db.String(5), nullable=False)
    salida = db.Column(db.String(5), nullable=False)

db.create_all()

@app.route('/', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        entrada = request.form['entrada']
        salida = request.form['salida']
        hoy = str(date.today())

        # Comprobar si ya hay registro
        if Registro.query.filter_by(nombre=nombre, fecha=hoy).first():
            flash('Ya registraste tus horas hoy', 'error')
            return redirect(url_for('registro'))

        nuevo_registro = Registro(nombre=nombre, fecha=hoy, entrada=entrada, salida=salida)
        db.session.add(nuevo_registro)
        db.session.commit()

        # Enviar correo
        msg = Message('Nuevo registro de horas', sender=os.getenv('MAIL_USERNAME'),
                      recipients=[os.getenv('MAIL_USERNAME')])
        msg.body = f"{nombre} registró entrada: {entrada}, salida: {salida} el {hoy}"
        mail.send(msg)

        # Enviar WhatsApp
        client.messages.create(
            body=f"{nombre} registró entrada: {entrada}, salida: {salida} el {hoy}",
            from_=TWILIO_WHATSAPP_FROM,
            to=WHATSAPP_TO
        )

        flash('Horas registradas correctamente', 'success')
        return redirect(url_for('registro'))

    return render_template('registro.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    auth = request.authorization
    if not auth or auth.username != os.getenv('ADMIN_USER') or auth.password != os.getenv('ADMIN_PASS'):
        return "No autorizado", 401

    registros = Registro.query.all()
    return render_template('admin.html', registros=registros)

if __name__ == '__main__':
    app.run(debug=True)
