from flask import Flask, render_template, request, redirect, url_for, session
import pyotp

from prometheus_client import Counter, generate_latest
from flask import Response

app = Flask(__name__)
app.secret_key = "petshop-secret-key"

# Credenciales fijas
USERNAME = "admin"
PASSWORD = "Petshop1"

# MFA
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
totp = pyotp.TOTP(TOTP_SECRET)

# Métricas
login_success_total = Counter(
    "login_success_total",
    "Cantidad de logins exitosos"
)

login_fail_total = Counter(
    "login_fail_total",
    "Cantidad de logins fallidos"
)

products = [
    {"id": 1, "name": "Concentrado Premium", "price": "$120.000"},
    {"id": 2, "name": "Cama para Mascotas", "price": "$85.000"},
    {"id": 3, "name": "Juguete Mordedor", "price": "$25.000"},
    {"id": 4, "name": "Correa Ajustable", "price": "$40.000"},
    {"id": 5, "name": "Arena para Gatos", "price": "$35.000"},
    {"id": 6, "name": "Shampoo Canino", "price": "$28.000"}
]


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return render_template(
            "login.html",
            error="Todos los campos son obligatorios."
        )

    if username == USERNAME and password == PASSWORD:
        session["authenticated"] = True
        login_success_total.inc()
        return redirect(url_for("mfa"))

    login_fail_total.inc()

    return render_template(
        "login.html",
        error="Usuario o contraseña incorrectos."
    )


@app.route("/mfa")
def mfa():

    if not session.get("authenticated"):
        return redirect(url_for("index"))

    return render_template("mfa.html")


@app.route("/verify", methods=["POST"])
def verify():

    if not session.get("authenticated"):
        return redirect(url_for("index"))

    otp = request.form.get("otp", "").strip()

    if not otp:
        return render_template(
            "mfa.html",
            error="Debe ingresar el código OTP."
        )

    if totp.verify(otp):
        session["mfa_verified"] = True
        return redirect(url_for("products_page"))

    return render_template(
        "mfa.html",
        error="Código OTP inválido."
    )


@app.route("/products")
def products_page():

    if not session.get("mfa_verified"):
        return redirect(url_for("index"))

    return render_template(
        "products.html",
        products=products
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("index"))


@app.route("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype="text/plain"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)