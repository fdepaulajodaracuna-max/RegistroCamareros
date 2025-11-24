import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

# Configuración Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "camarero_login"

DB_NAME = "trevian_app.db"
HORA_PRECIO = 9  # 9€ por hora

# Twilio
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM")
ADMIN_WHATSAPP_TO = os.environ.get("ADMIN_WHATSAPP_TO")  # Pon tu número en Render

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- DB setup ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Camareros
    c.execute("""CREATE TABLE IF NOT EXISTS camareros (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 nombre TEXT NOT NULL,
                 telefono TEXT UNIQUE NOT NULL
                 )""")
    # Registros de fichaje
    c.execute("""CREATE TABLE IF NOT EXISTS registros (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 camarero_id INTEGER,
                 fecha TEXT,
                 hora_entrada TEXT,
                 hora_salida TEXT,
                 coche INTEGER DEFAULT 0,
                 extra_coche INTEGER DEFAULT 0,
                 FOREIGN KEY(camarero_id) REFERENCES camareros(id)
                 )""")
    conn.commit()
    conn.close()

init_db()

# --- User class ---
class Camarero(UserMixin):
    def __init__(self, id_, nombre, telefono):
        self.id = id_
        self.nombre = nombre
        self.telefono = telefono

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM camareros WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return Camarero(row[0], row[1], row[2])
    return None

# --- Rutas ---
@app.route("/")
def index():
    return render_template("index.html")

# Registro y login camarero
@app.route("/camarero/register", methods=["GET", "POST"])
def camarero_register():
    if request.method == "POST":
        nombre = request.form["nombre"]
        telefono = request.form["telefono"]
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO camareros (nombre, telefono) VALUES (?, ?)", (nombre, telefono))
            conn.commit()
            flash("Registrado correctamente, ya puedes fichar.")
            return redirect(url_for("camarero_login"))
        except sqlite3.IntegrityError:
            flash("Teléfono ya registrado.")
        finally:
            conn.close()
    return render_template("camarero_register.html")

@app.route("/camarero/login", methods=["GET", "POST"])
def camarero_login():
    if request.method == "POST":
        telefono = request.form["telefono"]
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM camareros WHERE telefono=?", (telefono,))
        row = c.fetchone()
        conn.close()
        if row:
            user = Camarero(row[0], row[1], row[2])
            login_user(user)
            return redirect(url_for("camarero_dashboard"))
        else:
            flash("Teléfono no registrado.")
    return render_template("camarero_login.html")

@app.route("/camarero/dashboard", methods=["GET", "POST"])
@login_required
def camarero_dashboard():
    if request.method == "POST":
        fecha = request.form["fecha"]
        hora_entrada = request.form["hora_entrada"]
        hora_salida = request.form["hora_salida"]
        coche = int(request.form.get("coche", 0))
        extra_coche = int(request.form.get("extra_coche", 0))
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO registros (camarero_id, fecha, hora_entrada, hora_salida, coche, extra_coche) VALUES (?, ?, ?, ?, ?, ?)",
                  (current_user.id, fecha, hora_entrada, hora_salida, coche, extra_coche))
        conn.commit()
        conn.close()
        # Enviar WhatsApp
        mensaje = f"Camarero: {current_user.nombre}\nFecha: {fecha}\nEntrada: {hora_entrada}\nSalida: {hora_salida}\nCoche: {'Sí' if coche else 'No'}\nExtra coche: {extra_coche}€"
        try:
            client.messages.create(
                body=mensaje,
                from_=f"whatsapp:{TWILIO_WHATSAPP_FROM}",
                to=f"whatsapp:{ADMIN_WHATSAPP_TO}"
            )
        except Exception as e:
            print("Error enviando WhatsApp:", e)
        flash("Fichaje registrado.")
    return render_template("camarero_dashboard.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# --- Admin ---
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form["password"]
        if password == ADMIN_PASSWORD:
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Contraseña incorrecta.")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""SELECT r.id, c.nombre, r.fecha, r.hora_entrada, r.hora_salida, r.coche, r.extra_coche 
                 FROM registros r JOIN camareros c ON r.camarero_id = c.id""")
    registros = c.fetchall()
    # Opciones extra coche 0,5,10,...50
    opciones = list(range(0, 55, 5))
    conn.close()
    return render_template("admin_dashboard.html", registros=registros, opciones=opciones, tarifa=HORA_PRECIO)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect(url_for("admin_login"))

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

