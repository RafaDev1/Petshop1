# app.py
import os
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import pyotp, qrcode, io, base64
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import multiprocess, CollectorRegistry

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET", "change_this_secret_for_prod")

# Configuración de la DB desde variables de entorno
# Espera: DB_USER, DB_PASSWORD, DB_SERVER, DB_NAME
db_user = os.environ.get("DB_USER", "sa")
db_password = os.environ.get("DB_PASSWORD", "YourStrong!Passw0rd")
db_server = os.environ.get("DB_SERVER", "petshopsql.database.windows.net")
db_name = os.environ.get("DB_NAME", "PetShopDB")

# Usamos pyodbc driver 18; escape de caracteres en password si necesario
# SQLAlchemy URI para SQL Server
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mssql+pyodbc://{db_user}:{db_password}@{db_server}/{db_name}"
    "?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo Usuario
class User(db.Model):
    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    real_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    totp_secret = db.Column(db.String(32), nullable=False)

# Métricas Prometheus
login_success_total = Counter("petshop_login_success_total", "Total logins exitosos")
login_fail_total = Counter("petshop_login_fail_total", "Total logins fallidos")
requests_total = Counter("petshop_requests_total", "Total peticiones recibidas", ['endpoint'])

@app.before_request
def before_request_metrics():
    # Incrementa contador por endpoint
    try:
        endpoint = request.path
        requests_total.labels(endpoint=endpoint).inc()
    except Exception:
        pass

@app.route("/signin", methods=["GET","POST"])
def signin():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        real_name = request.form["real_name"]
        address = request.form["address"]
        phone = request.form["phone"]

        if User.query.filter_by(username=username).first():
            return "Usuario ya existe", 400

        secret = pyotp.random_base32()
        user = User(username=username, password=password, real_name=real_name, address=address, phone=phone, totp_secret=secret)
        db.session.add(user)
        db.session.commit()

        otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name="PetShop")
        qr = qrcode.make(otp_uri)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        return render_template("signin.html", qr_b64=qr_b64, registered=True)
    return render_template("signin.html", registered=False)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["login_ok"] = True
            session["username"] = username
            login_success_total.inc()
            return redirect("/mfa")
        else:
            login_fail_total.inc()
            return render_template("login.html", error="Credenciales inválidas")
    return render_template("login.html")

@app.route("/mfa", methods=["GET","POST"])
def mfa():
    if not session.get("login_ok"):
        return redirect("/login")
    if request.method == "POST":
        otp = request.form["otp"].strip()
        user = User.query.filter_by(username=session["username"]).first()
        if user and pyotp.TOTP(user.totp_secret).verify(otp):
            session["mfa_ok"] = True
            return redirect("/products")
        else:
            return render_template("mfa.html", error="OTP inválido")
    return render_template("mfa.html")

@app.route("/products")
def products():
    if not session.get("login_ok") or not session.get("mfa_ok"):
        return redirect("/login")
    productos = [
        {"nombre":"Collar","precio":"$10"},
        {"nombre":"Comida","precio":"$20"},
        {"nombre":"Juguete","precio":"$15"},
        {"nombre":"Cama","precio":"$50"},
        {"nombre":"Arena","precio":"$12"},
    ]
    return render_template("products.html", productos=productos)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/metrics")
def metrics():
    # Responder métricas Prometheus
    registry = CollectorRegistry()
    # Si usas multiprocess mode en App Service, necesitarías configurar multiprocess; para demo simple usamos default
    from prometheus_client import generate_latest
    resp = generate_latest()
    return (resp, 200, {'Content-Type': CONTENT_TYPE_LATEST})

if __name__ == "__main__":
    # Crear tablas si no existen (solo para desarrollo)
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
