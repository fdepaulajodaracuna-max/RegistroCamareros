from flask import Flask, request, redirect, url_for, render_template_string
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Time, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta

# ----------------------------
# CONFIGURACIÓN
# ----------------------------
app = Flask(__name__)
HOURLY_RATE = 9  # €/hora
DATABASE_URL = "sqlite:///trevian.db"

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# ----------------------------
# MODELOS
# ----------------------------
class Camarero(Base):
    __tablename__ = "camareros"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    telefono = Column(String)
    email = Column(String)
    fichajes = relationship("Fichaje", back_populates="camarero", cascade="all, delete-orphan")

class Fichaje(Base):
    __tablename__ = "fichajes"
    id = Column(Integer, primary_key=True)
    camarero_id = Column(Integer, ForeignKey('camareros.id'), nullable=False)
    fecha = Column(Date, nullable=False)
    entrada = Column(Time, nullable=False)
    salida = Column(Time, nullable=False)
    extra_coche = Column(Float, default=0.0)
    notas = Column(String)
    camarero = relationship("Camarero", back_populates="fichajes")

Base.metadata.create_all(engine)

# ----------------------------
# PLANTILLAS HTML
# ----------------------------
# Inicio
inicio_html = """
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Trevián Catering</title></head>
<body>
    <h1>¡Bienvenido a Trevián Catering!</h1>
    <ul>
        <li><a href="{{ url_for('gestionar_camareros') }}">Gestión de camareros</a></li>
        <li><a href="{{ url_for('gestionar_fichajes') }}">Registro de fichajes</a></li>
        <li><a href="{{ url_for('nominas') }}">Nóminas</a></li>
    </ul>
</body>
</html>
"""

# Camareros
camareros_html = """
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Camareros</title></head>
<body>
    <h1>Gestión de camareros</h1>
    <form method="post" action="{{ url_for('añadir_camarero') }}">
        Nombre: <input type="text" name="nombre" required>
        Teléfono: <input type="text" name="telefono">
        Email: <input type="text" name="email">
        <input type="submit" value="Añadir camarero">
    </form>
    <h2>Lista de camareros</h2>
    <ul>
        {% for cam in camareros %}
            <li>{{ cam.nombre }} - {{ cam.telefono }} - {{ cam.email }}
                <a href="{{ url_for('eliminar_camarero', camarero_id=cam.id) }}" onclick="return confirm('¿Eliminar camarero?')">[Eliminar]</a>
            </li>
        {% endfor %}
    </ul>
    <a href="{{ url_for('inicio') }}">Volver al inicio</a>
</body>
</html>
"""

# Fichajes
fichajes_html = """
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Fichajes</title></head>
<body>
    <h1>Registro de fichajes</h1>
    <form method="post" action="{{ url_for('añadir_fichaje') }}">
        Camarero:
        <select name="camarero">
            {% for cam in camareros %}
            <option value="{{ cam.id }}">{{ cam.nombre }}</option>
            {% endfor %}
        </select><br>
        Fecha: <input type="date" name="fecha" required><br>
        Entrada: <input type="time" name="entrada" required><br>
        Salida: <input type="time" name="salida" required><br>
        Extra coche (€): <input type="number" name="extra_coche" step="0.01" value="0"><br>
        Notas: <input type="text" name="notas"><br>
        <input type="submit" value="Registrar fichaje">
    </form>
    <h2>Fichajes registrados</h2>
    <ul>
        {% for f in fichajes %}
            <li>{{ f.fecha }} - {{ f.entrada }} a {{ f.salida }} - {{ f.camarero.nombre }} - Extra: €{{ f.extra_coche }}
                <a href="{{ url_for('eliminar_fichaje', fichaje_id=f.id) }}" onclick="return confirm('¿Eliminar fichaje?')">[Eliminar]</a>
            </li>
        {% endfor %}
    </ul>
    <a href="{{ url_for('inicio') }}">Volver al inicio</a>
</body>
</html>
"""

# Nóminas con separación por año y mes
nominas_html = """
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Nóminas</title></head>
<body>
    <h1>Nóminas</h1>
    {% for año, meses in datos.items() %}
        <h2>Año {{ año }}</h2>
        {% for mes, filas in meses.items() %}
            <h3>Mes {{ mes }}</h3>
            <table border="1">
                <tr>
                    <th>Camarero</th><th>Fecha</th><th>Entrada</th><th>Salida</th>
                    <th>Horas</th><th>Extra coche</th><th>Total €</th>
                </tr>
                {% for fila in filas %}
                <tr>
                    <td>{{ fila['Camarero'] }}</td>
                    <td>{{ fila['Fecha'] }}</td>
                    <td>{{ fila['Entrada'] }}</td>
                    <td>{{ fila['Salida'] }}</td>
                    <td>{{ fila['Horas'] }}</td>
                    <td>{{ fila['Extra coche'] }}</td>
                    <td>{{ fila['Total'] }}</td>
                </tr>
                {% endfor %}
            </table>
        {% endfor %}
    {% endfor %}
    <a href="{{ url_for('inicio') }}">Volver al inicio</a>
</body>
</html>
"""

# ----------------------------
# RUTAS DE FLASK
# ----------------------------
@app.route('/')
def inicio():
    return render_template_string(inicio_html)

@app.route('/camareros')
def gestionar_camareros():
    with Session() as session:
        lista = session.query(Camarero).all()
        return render_template_string(camareros_html, camareros=lista)

@app.route('/camareros/añadir', methods=['POST'])
def añadir_camarero():
    with Session() as session:
        nuevo = Camarero(
            nombre=request.form['nombre'],
            telefono=request.form.get('telefono',''),
            email=request.form.get('email','')
        )
        session.add(nuevo)
        session.commit()
    return redirect(url_for('gestionar_camareros'))

@app.route('/camareros/eliminar/<int:camarero_id>')
def eliminar_camarero(camarero_id):
    with Session() as session:
        cam = session.get(Camarero, camarero_id)
        if cam:
            session.delete(cam)
            session.commit()
    return redirect(url_for('gestionar_camareros'))

@app.route('/fichajes')
def gestionar_fichajes():
    with Session() as session:
        camareros = session.query(Camarero).all()
        fichajes = session.query(Fichaje).all()
        return render_template_string(fichajes_html, camareros=camareros, fichajes=fichajes)

@app.route('/fichajes/añadir', methods=['POST'])
def añadir_fichaje():
    with Session() as session:
        nuevo = Fichaje(
            camarero_id=int(request.form['camarero']),
            fecha=datetime.strptime(request.form['fecha'], "%Y-%m-%d").date(),
            entrada=datetime.strptime(request.form['entrada'], "%H:%M").time(),
            salida=datetime.strptime(request.form['salida'], "%H:%M").time(),
            extra_coche=float(request.form.get('extra_coche',0)),
            notas=request.form.get('notas','')
        )
        session.add(nuevo)
        session.commit()
    return redirect(url_for('gestionar_fichajes'))

@app.route('/fichajes/eliminar/<int:fichaje_id>')
def eliminar_fichaje(fichaje_id):
    with Session() as session:
        f = session.get(Fichaje, fichaje_id)
        if f:
            session.delete(f)
            session.commit()
    return redirect(url_for('gestionar_fichajes'))

@app.route('/nominas')
def nominas():
    with Session() as session:
        fichajes = session.query(Fichaje).all()
        datos = {}
        for f in fichajes:
            # Cálculo de horas
            entrada_dt = datetime.combine(f.fecha, f.entrada)
            salida_dt = datetime.combine(f.fecha, f.salida)
            if salida_dt < entrada_dt:
                salida_dt += timedelta(days=1)
            horas = (salida_dt - entrada_dt).total_seconds() / 3600
            total = horas * HOURLY_RATE + f.extra_coche

            año = f.fecha.year
            mes = f.fecha.month
            if año not in datos:
                datos[año] = {}
            if mes not in datos[año]:
                datos[año][mes] = []

            datos[año][mes].append({
                "Camarero": f.camarero.nombre,
                "Fecha": f.fecha,
                "Entrada": f.entrada,
                "Salida": f.salida,
                "Horas": round(horas,2),
                "Extra coche": round(f.extra_coche,2),
                "Total": round(total,2)
            })
        return render_template_string(nominas_html, datos=datos)

# ----------------------------
# INICIO DEL SERVIDOR
# ----------------------------
import os  # Esto permite leer variables del sistema

if __name__ == "__main__":
    # host="0.0.0.0" significa que la app es accesible desde fuera
    # port=int(os.environ.get("PORT", 5000)) usa el puerto que Render asigna
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

