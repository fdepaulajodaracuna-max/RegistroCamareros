from flask import Flask, request, redirect, url_for, render_template_string, session
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# Configuración Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM')
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Admin
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///camareros.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24)
db = SQLAlchemy(app)

# Modelo de camarero
class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    entrada = db.Column(db.String(10), nullable=False)
    salida = db.Column(db.String(10), nullable=False)
    fecha = db.Column(db.String(10), nullable=False)

db.create_all()

# Pantalla de registro para camareros
@app.route("/", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form['nombre']
        entrada = request.form['entrada']
        salida = request.form['salida']
        fecha = datetime.now().strftime("%Y-%m-%d")

        # Verificar que no haya registrado hoy
        if Registro.query.filter_by(nombre=nombre, fecha=fecha).first():
            return "Ya has registrado tus horas hoy."

        nuevo = Registro(nombre=nombre, entrada=entrada, salida=salida, fecha=fecha)
        db.session.add(nuevo)
        db.session.commit()

        # Enviar WhatsApp
        try:
            client.messages.create(
                from_=TWILIO_WHATSAPP_FROM,
                body=f"{nombre} registró entrada: {entrada}, salida: {salida} el {fecha}",
                to="whatsapp:+34631592283"
            )
        except Exception as e:
            print(f"Error notificando: {e}")

        return "Registro guardado correctamente."
    
    return render_template_string("""
    <h2>Registro de horas</h2>
    <form method="post">
        Nombre: <input type="text" name="nombre" required><br>
        Hora de entrada (HH:MM): <input type="text" name="entrada" required><br>
        Hora de salida (HH:MM): <input type="text" name="salida" required><br>
        <input type="submit" value="Registrar">
    </form>
    """)

# Panel de admin
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for("panel"))
        else:
            return "Contraseña incorrecta"

    return render_template_string("""
    <h2>Login Admin</h2>
    <form method="post">
        Contraseña: <input type="password" name="password" required><br>
        <input type="submit" value="Entrar">
    </form>
    """)

@app.route("/panel")
def panel():
    if not session.get('admin'):
        return redirect(url_for("admin"))

    registros = Registro.query.all()
    html = "<h2>Panel Admin</h2><table border=1><tr><th>Nombre</th><th>Entrada</th><th>Salida</th><th>Fecha</th></tr>"
    for r in registros:
        html += f"<tr><td>{r.nombre}</td><td>{r.entrada}</td><td>{r.salida}</td><td>{r.fecha}</td></tr>"
    html += "</table>"
    return html

if __name__ == "__main__":
    app.run(debug=True)
