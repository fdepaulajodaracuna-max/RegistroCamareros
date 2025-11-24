from flask import Flask, request, render_template_string
from datetime import datetime
import os
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
registro_horas = {}  # {nombre: fecha_registro}

# --- FUNCIONES DE NOTIFICACIÓN ---
def enviar_whatsapp(mensaje, numero_destino):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    client = Client(account_sid, auth_token)
    client.messages.create(
        body=mensaje,
        from_='whatsapp:+14155238886',
        to=f'whatsapp:{numero_destino}'
    )

def enviar_correo(asunto, cuerpo, destino):
    remitente = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    msg = MIMEText(cuerpo)
    msg['Subject'] = asunto
    msg['From'] = remitente
    msg['To'] = destino
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remitente, password)
        server.send_message(msg)

# --- RUTA PRINCIPAL ---
@app.route("/", methods=["GET", "POST"])
def index():
    mensaje = ""
    alert_type = "info"
    if request.method == "POST":
        camarero = request.form.get("camarero").strip()
        accion = request.form.get("accion")
        hoy = datetime.now().date()

        if registro_horas.get(camarero) == hoy:
            mensaje = "Ya registraste tus horas hoy."
            alert_type = "warning"
        else:
            registro_horas[camarero] = hoy
            hora_actual = datetime.now().strftime("%H:%M:%S")
            mensaje = f"{camarero} registró {accion} a las {hora_actual}"
            alert_type = "success"

            try:
                enviar_whatsapp(mensaje, os.environ.get("WHATSAPP_NUMERO"))
                enviar_correo("Registro de horas", mensaje, os.environ.get("EMAIL_DESTINO"))
            except Exception as e:
                mensaje += f" (Error notificando: {e})"
                alert_type = "danger"

    html = """
    <!doctype html>
    <html lang="es">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Registro de Horas</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');

            body {
                margin:0;
                height:100vh;
                font-family: 'Roboto', sans-serif;
                background: linear-gradient(-45deg, #4facfe, #00f2fe, #43e97b, #38f9d7);
                background-size: 400% 400%;
                animation: gradientBG 15s ease infinite;
                display: flex;
                justify-content: center;
                align-items: center;
            }

            @keyframes gradientBG {
                0%{background-position:0% 50%}
                50%{background-position:100% 50%}
                100%{background-position:0% 50%}
            }

            .card {
                padding: 2rem;
                border-radius: 1.5rem;
                box-shadow: 0 0 40px rgba(0,0,0,0.3);
                width: 100%;
                max-width: 400px;
                background: rgba(255,255,255,0.95);
                text-align: center;
                transition: transform 0.3s ease;
            }

            .card:hover {
                transform: translateY(-10px);
            }

            h1 {
                font-weight: 700;
                margin-bottom: 1.5rem;
                color: #333;
            }

            .btn-entrada {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                transition: transform 0.2s;
            }

            .btn-entrada:hover {
                transform: scale(1.05);
            }

            .btn-salida {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                transition: transform 0.2s;
            }

            .btn-salida:hover {
                transform: scale(1.05);
            }
        </style>
      </head>
      <body>
        <div class="card">
          <h1>Registro de Horas</h1>
          <form method="post">
            <input type="text" class="form-control mb-3" name="camarero" placeholder="Tu nombre" required>
            <div class="d-grid gap-2">
              <button type="submit" name="accion" value="entrada" class="btn btn-entrada btn-lg">Entrada</button>
              <button type="submit" name="accion" value="salida" class="btn btn-salida btn-lg">Salida</button>
            </div>
          </form>
          {% if mensaje %}
          <div class="alert alert-{{ alert_type }} mt-3 text-center" role="alert">
            {{ mensaje }}
          </div>
          {% endif %}
        </div>
      </body>
    </html>
    """
    return render_template_string(html, mensaje=mensaje, alert_type=alert_type)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
