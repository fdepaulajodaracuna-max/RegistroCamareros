import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin
import sqlite3
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"

DATABASE = "trevian_app.db"

# ----------------- MODELO USER ADMIN -----------------
class Admin(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return Admin(user_id)

# ----------------- BASE DE DATOS -----------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Tabla camareros
    c.execute('''CREATE TABLE IF NOT EXISTS camareros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT,
                    telefono TEXT
                )''')
    # Tabla registros
    c.execute('''CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camarero_id INTEGER,
                    fecha TEXT,
                    hora_entrada TEXT,
                    hora_salida TEXT,
                    extra_coche REAL DEFAULT 0
                )''')
    # Tabla admin
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT,
                    password TEXT
                )''')
    # Crear usuario admin por defecto si no existe
    c.execute("SELECT * FROM admin WHERE usuario='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admin (usuario, password) VALUES (?, ?)", ('admin', '1234'))
    conn.commit()
    conn.close()

init_db()

# ----------------- FUNCIONES -----------------
def send_whatsapp(to, message):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM")
    client = Client(account_sid, auth_token)
    client.messages.create(
        body=message,
        from_=from_whatsapp,
        to=f'whatsapp:{to}'
    )

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- RUTAS -----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        hora_entrada = request.form['hora_entrada']
        hora_salida = request.form['hora_salida']
        fecha = datetime.now().strftime("%Y-%m-%d")

        conn = get_db_connection()
        # Verificar si camarero existe
        c = conn.cursor()
        c.execute("SELECT id FROM camareros WHERE nombre=? AND telefono=?", (nombre, telefono))
        res = c.fetchone()
        if res:
            camarero_id = res[0]
        else:
            c.execute("INSERT INTO camareros (nombre, telefono) VALUES (?, ?)", (nombre, telefono))
            camarero_id = c.lastrowid
            conn.commit()

        # Verificar si ya registró hoy
        c.execute("SELECT * FROM registros WHERE camarero_id=? AND fecha=?", (camarero_id, fecha))
        if c.fetchone():
            flash("Ya has registrado tu jornada hoy.", "danger")
            conn.close()
            return redirect(url_for("index"))

        # Insertar registro
        c.execute("INSERT INTO registros (camarero_id, fecha, hora_entrada, hora_salida) VALUES (?, ?, ?, ?)",
                  (camarero_id, fecha, hora_entrada, hora_salida))
        conn.commit()
        conn.close()

        # Enviar WhatsApp
        try:
            send_whatsapp(telefono, f"Hola {nombre}, tu registro de entrada ({hora_entrada}) y salida ({hora_salida}) ha sido guardado.")
        except Exception as e:
            print("Error Twilio:", e)

        flash("Registro guardado correctamente.", "success")
        return redirect(url_for("index"))

    return render_template("index.html")

# ----------------- LOGIN ADMIN -----------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        usuario = request.form['usuario']
        password = request.form['password']
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE usuario=? AND password=?", (usuario, password))
        res = c.fetchone()
        conn.close()
        if res:
            admin = Admin(res[0])
            login_user(admin)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")
            return redirect(url_for("admin_login"))
    return render_template("admin.html")

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT r.id, c.nombre, c.telefono, r.fecha, r.hora_entrada, r.hora_salida, r.extra_coche 
                 FROM registros r 
                 JOIN camareros c ON r.camarero_id = c.id
                 ORDER BY r.fecha DESC''')
    registros = c.fetchall()
    conn.close()
    return render_template("admin.html", registros=registros)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin_login"))

# ----------------- NÓMINAS -----------------
@app.route("/admin/nominas")
@login_required
def nominas():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT c.nombre, strftime('%Y', r.fecha) AS año, strftime('%m', r.fecha) AS mes,
                        SUM((julianday(r.hora_salida)-julianday(r.hora_entrada))*24) AS horas,
                        SUM(r.extra_coche) AS extra
                 FROM registros r
                 JOIN camareros c ON r.camarero_id=c.id
                 GROUP BY c.nombre, año, mes
                 ORDER BY año DESC, mes DESC''')
    datos = c.fetchall()
    conn.close()
    return render_template("admin.html", nominas=datos)

# ----------------- RUN APP -----------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # usa el puerto de Render o 5000 local
    app.run(host="0.0.0.0", port=port)
