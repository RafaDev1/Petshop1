from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
import pyotp, qrcode, io, base64
from prometheus_client import Counter, generate_latest

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configuración Azure SQL Database
app.config['SQLALCHEMY_DATABASE_URI'] = "mssql+pyodbc://usuario:password@petshopsql.database.windows.net/PetShopDB?driver=ODBC+Driver+18+for+SQL+Server"
db = SQLAlchemy(app)

# Modelo Usuario
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    real_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    totp_secret = db.Column(db.String(32), nullable=False)

# Métricas Prometheus
login_success_total = Counter("login_success_total", "Total logins exitosos")
login_fail_total = Counter("login_fail_total", "Total logins fallidos")

@app.route("/signin", methods=["GET","POST"])
def signin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        real_name = request.form["real_name"]
        address = request.form["address"]
        phone = request.form["phone"]

        if User.query.filter_by(username=username).first():
            return "Usuario ya existe"

        secret = pyotp.random_base32()
        user = User(username=username, password=password, real_name=real_name, address=address, phone=phone, totp_secret=secret)
        db.session.add(user)
        db.session.commit()

        otp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name="PetShop")
        qr = qrcode.make(otp_uri)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        return f"<h3>Registro exitoso</h3><img src='data:image/png;base64,{qr_b64}'/><br><a href='/login'>Ir al Login</a>"
    return render_template("signin.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["login_ok"] = True
            session["username"] = username
            login_success_total.inc()
            return redirect("/mfa")
        else:
            login_fail_total.inc()
            return "Credenciales inválidas"
    return render_template("login.html")

@app.route("/mfa", methods=["GET","POST"])
def mfa():
    if request.method == "POST":
        otp = request.form["otp"]
        user = User.query.filter_by(username=session["username"]).first()
        if pyotp.TOTP(user.totp_secret).verify(otp):
            session["mfa_ok"] = True
            return redirect("/products")
        else:
            return "OTP inválido"
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
        {"nombre":"Transportadora","precio":"$40"},
        {"nombre":"Shampoo","precio":"$8"},
        {"nombre":"Plato","precio":"$5"},
        {"nombre":"Correa","precio":"$18"},
        {"nombre":"Snacks","precio":"$7"},
    ]
    return render_template("products.html", productos=productos)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/metrics")
def metrics():
    return generate_latest()
