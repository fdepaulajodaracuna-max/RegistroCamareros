import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# Configuración Twilio
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM")
TWILIO_TO_NUMBER = os.environ.get("TWILIO_TO_NUMBER")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "camarero_login"

DB_PATH = "trevian_app.db"
HORA_PRECIO = 9

# --- Usuario camarero ---
class Camarero(UserMixin):
    def __init__(self, id_, nombre, telefono):
        self.id = id_
        self.nombre = nombre
        self.telefono = telefono

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nombre, telefono FROM camareros WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return Camarero(row[0], row[1], row[2])
    return None

# --- RUTAS ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/camarero/register", methods=["GET", "POST"])
def camarero_register():
    if request.method == "POST":
        nombre = request.form["nombre"]
        telefono = request.form["telefono"]
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Evitar duplicados
        c.execute("SELECT id FROM camareros WHERE telefono=?", (telefono,))
        if c.fetchone():
            flash("Este teléfono ya está registrado")
            conn.close()
            return redirect(url_for("camarero_register"))
        c.execute("INSERT INTO camareros (nombre, telefono) VALUES (?, ?)", (nombre, telefono))
        conn.commit()
        conn.close()
        flash("Registro completado. Ahora inicia sesión.")
        return redirect(url_for("camarero_login"))
    return render_template("camarero_register.html")

@app.route("/camarero/login", methods=["GET", "POST"])
def camarero_login():
    if request.method == "POST":
        telefono = request.form["telefono"]
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre FROM camareros WHERE telefono=?", (telefono,))
        row = c.fetchone()
        conn.close()
        if row:
            user = Camarero(row[0], row[1], telefono)
            login_user(user)
            return redirect(url_for("camarero_dashboard"))
        else:
            flash("Teléfono no registrado")
    return render_template("camarero_login.html")

@app.route("/camarero/dashboard")
@login_required
def camarero_dashboard():
    return render_template("camarero_dashboard.html", nombre=current_user.nombre)

@app.route("/camarero/fichar", methods=["GET", "POST"])
@login_required
def fichar():
    if request.method == "POST":
        fecha = request.form["fecha"]
        entrada = request.form["entrada"]
        salida = request.form["salida"]
        coche = request.form.get("coche") == "SI"
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO registros (camarero_id, fecha, entrada, salida, coche, extra_coche) VALUES (?, ?, ?, ?, ?, ?)",
            (current_user.id, fecha, entrada, salida, int(coche), 0)
        )
        conn.commit()
        conn.close()

        # Enviar WhatsApp
        mensaje = f"{current_user.nombre} fichó hoy {fecha}.\nEntrada: {entrada}\nSalida: {salida}\nPuso coche: {'SI' if coche else 'NO'}"
        try:
            client.messages.create(
                body=mensaje,
                from_=f"whatsapp:{TWILIO_WHATSAPP_FROM}",
                to=f"whatsapp:{TWILIO_TO_NUMBER}"
            )
        except Exception as e:
            print("Error enviando WhatsApp:", e)

        flash("Fichaje registrado")
        return redirect(url_for("camarero_dashboard"))
    return render_template("fichar.html")

@app.route("/camarero/logout")
@login_required
def camarero_logout():
    logout_user()
    return redirect(url_for("index"))

# --- ADMIN ---

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form["user"]
        password = request.form["password"]
        if user == os.environ.get("ADMIN_USER") and password == os.environ.get("ADMIN_PASS"):
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Credenciales incorrectas")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT r.id, c.nombre, r.fecha, r.entrada, r.salida, r.coche, r.extra_coche
        FROM registros r
        JOIN camareros c ON r.camarero_id = c.id
        ORDER BY r.fecha DESC
    """)
    registros = c.fetchall()
    conn.close()
    return render_template("admin_dashboard.html", registros=registros, tarifa=HORA_PRECIO)

@app.route("/admin/extra_coche/<int:id>", methods=["POST"])
def admin_extra_coche(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))
    extra = int(request.form["extra"])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE registros SET extra_coche=? WHERE id=?", (extra, id))
    conn.commit()
    conn.close()
    flash("Extra coche actualizado")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/nominas")
def admin_nominas():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT c.nombre, r.fecha, r.entrada, r.salida, r.coche, r.extra_coche
        FROM registros r
        JOIN camareros c ON r.camarero_id = c.id
    """)
    registros = c.fetchall()
    nominas = {}
    for nombre, fecha, entrada, salida, coche, extra in registros:
        h_entrada, m_entrada = map(int, entrada.split(":"))
        h_salida, m_salida = map(int, salida.split(":"))
        horas = h_salida + m_salida/60 - (h_entrada + m_entrada/60)
        pago = horas*HORA_PRECIO + (extra if coche else 0)
        if nombre not in nominas:
            nominas[nombre] = []
        nominas[nombre].append({"fecha": fecha, "horas": round(horas,2), "pago": round(pago,2)})
    conn.close()
    return render_template("admin_nominas.html", nominas=nominas)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
