import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin
import sqlite3
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv

# load .env locally (Render uses env vars)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "cambia_esto_localmente")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"

DATABASE = "trevian_app.db"

# ----------------- ADMIN USER -----------------
class Admin(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return Admin(user_id)

# ----------------- DB -----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # camareros: ahora con password (simple)
    c.execute('''CREATE TABLE IF NOT EXISTS camareros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT,
                    telefono TEXT UNIQUE,
                    password TEXT
                )''')
    # registros
    c.execute('''CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camarero_id INTEGER,
                    fecha TEXT,
                    hora_entrada TEXT,
                    hora_salida TEXT,
                    coche INTEGER DEFAULT 0,
                    extra_coche REAL DEFAULT 0
                )''')
    # admin
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT UNIQUE,
                    password TEXT
                )''')
    # config (precio base del coche no necesario, extras por registro controlados por admin)
    c.execute('''CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value REAL
                )''')
    # seed admin and default config
    c.execute("SELECT * FROM admin WHERE usuario='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admin (usuario, password) VALUES (?, ?)", ('admin', '1234'))
    # seed precio por defecto (si quieres usarlo)
    c.execute("SELECT * FROM config WHERE key='precio_coche'")
    if not c.fetchone():
        c.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('precio_coche', 0))
    conn.commit()
    conn.close()

init_db()

# ----------------- TWILIO SEND -----------------
def send_notification_to_admin(message):
    """
    Envía notificación al admin por SMS o WhatsApp según ADMIN_NOTIFY_METHOD.
    - ADMIN_NOTIFY_METHOD: 'whatsapp' o 'sms'
    - ADMIN_PHONE: +34...
    - TWILIO_WHATSAPP_FROM: (ej. whatsapp:+1415...)
    - TWILIO_SMS_FROM: +1...
    """
    method = os.getenv("ADMIN_NOTIFY_METHOD", "whatsapp").lower()
    admin_phone = os.getenv("ADMIN_PHONE")
    if not admin_phone:
        print("ADMIN_PHONE no configurado — no se envía notificación")
        return
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        print("Twilio no configurado")
        return
    client = Client(account_sid, auth_token)
    try:
        if method == "sms":
            from_number = os.getenv("TWILIO_SMS_FROM")
            if not from_number:
                print("TWILIO_SMS_FROM no configurado")
                return
            client.messages.create(body=message, from_=from_number, to=admin_phone)
        else:
            # whatsapp (por defecto)
            from_wh = os.getenv("TWILIO_WHATSAPP_FROM")
            if not from_wh:
                print("TWILIO_WHATSAPP_FROM no configurado")
                return
            client.messages.create(body=message, from_=f"whatsapp:{from_wh.replace('whatsapp:','') if 'whatsapp:' in from_wh else from_wh}", to=f"whatsapp:{admin_phone}")
    except Exception as e:
        print("Error enviando notificación Twilio:", e)

# ----------------- HELPERS -----------------
HORA_PRECIO = 9.0  # 9€ por hora, constante

def calcular_horas(entrada_h, salida_h):
    """entrada_h y salida_h en formato 'HH:MM' -> devuelve horas (float)"""
    try:
        f1 = datetime.strptime(entrada_h, "%H:%M")
        f2 = datetime.strptime(salida_h, "%H:%M")
        delta = (f2 - f1).seconds / 3600.0
        # si negativo (pasó medianoche) tratamos sumando 24h
        if delta < 0:
            delta += 24
        return round(delta, 2)
    except Exception:
        return 0.0

# ----------------- RUTAS PÚBLICAS (camareros) -----------------

@app.route("/")
def home():
    return render_template("home.html")

# Registro de camarero (primera vez)
@app.route("/camarero/register", methods=["GET", "POST"])
def camarero_register():
    if request.method == "POST":
        nombre = request.form['nombre'].strip()
        telefono = request.form['telefono'].strip()
        password = request.form['password'].strip()
        if not nombre or not telefono or not password:
            flash("Completa todos los campos", "danger")
            return redirect(url_for("camarero_register"))
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO camareros (nombre, telefono, password) VALUES (?, ?, ?)", (nombre, telefono, password))
            conn.commit()
            conn.close()
            flash("Registro completado. Ahora puedes iniciar sesión.", "success")
            return redirect(url_for("camarero_login"))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Ya existe un camarero con ese teléfono. Haz login.", "warning")
            return redirect(url_for("camarero_login"))
    return render_template("camarero_register.html")

# Login camarero
@app.route("/camarero/login", methods=["GET", "POST"])
def camarero_login():
    if request.method == "POST":
        telefono = request.form['telefono'].strip()
        password = request.form['password'].strip()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM camareros WHERE telefono=? AND password=?", (telefono, password))
        row = c.fetchone()
        conn.close()
        if row:
            # guardamos en session: id y nombre
            session['camarero_id'] = row['id']
            session['camarero_nombre'] = row['nombre']
            flash("Inicio de sesión correcto", "success")
            return redirect(url_for("camarero_dashboard"))
        else:
            flash("Credenciales incorrectas", "danger")
            return redirect(url_for("camarero_login"))
    return render_template("camarero_login.html")

# Logout camarero
@app.route("/camarero/logout")
def camarero_logout():
    session.pop('camarero_id', None)
    session.pop('camarero_nombre', None)
    flash("Desconectado", "info")
    return redirect(url_for("home"))

# Dashboard camarero: crear registro, ver registros propios
@app.route("/camarero/dashboard", methods=["GET", "POST"])
def camarero_dashboard():
    if 'camarero_id' not in session:
        flash("Inicia sesión primero", "warning")
        return redirect(url_for("camarero_login"))
    cid = session['camarero_id']
    conn = get_db_connection()
    c = conn.cursor()

    # crear nuevo registro
    if request.method == "POST":
        fecha = request.form['fecha']
        hora_entrada = request.form['hora_entrada']
        hora_salida = request.form.get('hora_salida', '').strip()
        coche = 1 if request.form.get('coche') == 'on' else 0

        # Un registro por camarero por fecha (si quieres permitir más, habría que cambiar)
        c.execute("SELECT * FROM registros WHERE camarero_id=? AND fecha=?", (cid, fecha))
        existing = c.fetchone()
        if existing:
            # Si ya existía y ahora se añade hora_salida (antes vacía), actualizamos y enviamos notificación
            prev_hora_salida = existing['hora_salida']
            if hora_salida and (not prev_hora_salida or prev_hora_salida == ""):
                # actualizar salida y coche y calcular extra si coche
                extra = float(existing['extra_coche'] or 0)
                if coche and extra == 0:
                    # si admin no ha fijado extra, lo dejamos 0 (admin puede editar)
                    extra = 0
                c.execute("UPDATE registros SET hora_salida=?, coche=?, extra_coche=? WHERE id=?",
                          (hora_salida, coche, extra, existing['id']))
                conn.commit()
                # enviar aviso al admin (solo al hacer la salida)
                nombre = session.get('camarero_nombre')
                msg = f"{nombre} ha fichado salida.\nFecha:{fecha}\nEntrada:{existing['hora_entrada']}\nSalida:{hora_salida}\nCoche:{'Sí' if coche else 'No'}"
                send_notification_to_admin(msg)
                flash("Salida registrada y administrador notificado", "success")
            else:
                flash("Ya existe un registro para esa fecha", "warning")
        else:
            # Insert new; if hora_salida provided, send notification immediately
            extra = 0.0
            c.execute("INSERT INTO registros (camarero_id, fecha, hora_entrada, hora_salida, coche, extra_coche) VALUES (?, ?, ?, ?, ?, ?)",
                      (cid, fecha, hora_entrada, hora_salida, coche, extra))
            conn.commit()
            # send notification only if salida provided
            if hora_salida:
                nombre = session.get('camarero_nombre')
                msg = f"{nombre} ha registrado su jornada.\nFecha:{fecha}\nEntrada:{hora_entrada}\nSalida:{hora_salida}\nCoche:{'Sí' if coche else 'No'}"
                send_notification_to_admin(msg)
            flash("Registro creado", "success")
    # get own registros
    c.execute("""SELECT r.*, c.nombre FROM registros r JOIN camareros c ON r.camarero_id=c.id
                 WHERE r.camarero_id=? ORDER BY r.fecha DESC""", (cid,))
    registros = c.fetchall()
    conn.close()
    return render_template("camarero_dashboard.html", registros=registros, tarifa=HORA_PRECIO)

# ----------------- RUTAS ADMIN -----------------

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        usuario = request.form['usuario']
        password = request.form['password']
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM admin WHERE usuario=? AND password=?", (usuario, password))
        row = c.fetchone()
        conn.close()
        if row:
            admin = Admin(row['id'])
            login_user(admin)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Usuario/contraseña incorrecto", "danger")
            return redirect(url_for("admin_login"))
    return render_template("admin_login.html")

@app.route("/admin/dashboard", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    conn = get_db_connection()
    c = conn.cursor()
    # Si admin edita extra_coche para un registro
    if request.method == "POST":
        reg_id = request.form.get("reg_id")
        extra = float(request.form.get("extra_coche", 0))
        c.execute("UPDATE registros SET extra_coche=? WHERE id=?", (extra, reg_id))
        conn.commit()
        flash("Extra coche actualizado", "success")
    # listar registros
    c.execute('''SELECT r.id, r.camarero_id, cam.nombre, cam.telefono, r.fecha, r.hora_entrada, r.hora_salida, r.coche, r.extra_coche
                 FROM registros r
                 JOIN camareros cam ON r.camarero_id = cam.id
                 ORDER BY r.fecha DESC''')
    registros = c.fetchall()
    conn.close()
    # opciones desplegable 0..100 step 5
    opciones = list(range(0, 105, 5))
    return render_template("admin_dashboard.html", registros=registros, opciones=opciones, tarifa=HORA_PRECIO)

@app.route("/admin/nominas")
@login_required
def admin_nominas():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT cam.nombre,
                        strftime('%Y', r.fecha) AS año,
                        strftime('%m', r.fecha) AS mes,
                        SUM((julianday(r.hora_salida)-julianday(r.hora_entrada))*24) AS horas,
                        SUM(r.extra_coche) AS extra
                 FROM registros r
                 JOIN camareros cam ON r.camarero_id = cam.id
                 WHERE r.hora_salida IS NOT NULL AND r.hora_salida <> ''
                 GROUP BY cam.nombre, año, mes
                 ORDER BY año DESC, mes DESC''')
    datos = c.fetchall()
    conn.close()
    # compute total € per row: horas*9 + extra (we'll pass tarifa)
    return render_template("nominas.html", nominas=datos, tarifa=HORA_PRECIO)

@app.route("/admin/lista_camareros")
@login_required
def admin_lista_camareros():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, nombre, telefono FROM camareros ORDER BY nombre")
    rows = c.fetchall()
    conn.close()
    return render_template("admin_camareros.html", camareros=rows)

@app.route("/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))

# ----------------- RUN -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
