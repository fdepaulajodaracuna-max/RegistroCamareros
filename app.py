from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------------------
# INIT DB
# ---------------------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Tabla de camareros
    c.execute("""
    CREATE TABLE IF NOT EXISTS camareros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        telefono TEXT UNIQUE,
        password TEXT,
        creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Entradas/salidas
    c.execute("""
    CREATE TABLE IF NOT EXISTS fichajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camarero_id INTEGER,
        hora_entrada TEXT,
        hora_salida TEXT,
        coche INTEGER DEFAULT 0,
        pago_coche INTEGER DEFAULT 0,
        FOREIGN KEY(camarero_id) REFERENCES camareros(id)
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------------------
# PAGINA PRINCIPAL
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------
# REGISTRO CAMARERO
# ---------------------------
@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        nombre = request.form["nombre"]
        telefono = request.form["telefono"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO camareros (nombre, telefono, password) VALUES (?, ?, ?)",
                  (nombre, telefono, password))
        conn.commit()
        conn.close()
        return redirect("/login")

    return render_template("registrar_camarero.html")


# ---------------------------
# LOGIN CAMARERO
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login_camarero():
    if request.method == "POST":
        telefono = request.form["telefono"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT id, nombre FROM camareros WHERE telefono=? AND password=?",
                  (telefono, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["camarero_id"] = user[0]
            session["camarero_nombre"] = user[1]
            return redirect("/fichar")
        else:
            return "Datos incorrectos"

    return render_template("login_camarero.html")


# ---------------------------
# FICHAR
# ---------------------------
@app.route("/fichar", methods=["GET", "POST"])
def fichar():
    if "camarero_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        accion = request.form["accion"]
        coche = int(request.form["coche"])
        pago_coche = int(request.form["pago_coche"])

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        if accion == "entrada":
            c.execute("INSERT INTO fichajes (camarero_id, hora_entrada, coche, pago_coche) VALUES (?, ?, ?, ?)",
                      (session["camarero_id"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), coche, pago_coche))

        elif accion == "salida":
            c.execute("""
                UPDATE fichajes
                SET hora_salida=?
                WHERE camarero_id=? AND hora_salida IS NULL
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session["camarero_id"]))

        conn.commit()
        conn.close()

        return redirect("/fichar")

    return render_template("fichar.html", nombre=session["camarero_nombre"])


# ---------------------------
# ADMIN LOGIN (FIJO)
# ---------------------------
@app.route("/admin")
def admin_login():
    # Admin fijo
    session["admin"] = True
    return redirect("/admin/dashboard")


# ---------------------------
# DASHBOARD ADMIN
# ---------------------------
@app.route("/admin/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/admin")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    SELECT f.id, c.nombre, f.hora_entrada, f.hora_salida, f.coche, f.pago_coche
    FROM fichajes f
    JOIN camareros c ON f.camarero_id = c.id
    ORDER BY f.id DESC
    """)
    fichajes = c.fetchall()

    conn.close()
    return render_template("dashboard_admin.html", fichajes=fichajes)


# ---------------------------
# LOGOUT CAMARERO
# ---------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
