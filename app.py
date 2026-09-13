from flask import Flask, render_template, request, redirect, url_for, session
import pyotp

app = Flask(__name__)
app.secret_key = "petshop-secret-key"

USERNAME = "admin"
PASSWORD = "Petshop1"

TOTP_SECRET = "JBSWY3DPEHPK3PXP"
totp = pyotp.TOTP(TOTP_SECRET)

PRODUCTS = [
    {"name": "Concentrado Premium", "price": "$120.000"},
    {"name": "Cama para Mascotas", "price": "$85.000"},
    {"name": "Correa Ajustable", "price": "$35.000"},
    {"name": "Shampoo Canino", "price": "$25.000"},
    {"name": "Arena para Gatos", "price": "$40.000"},
    {"name": "Rascador", "price": "$65.000"},
    {"name": "Juguete Mordedor", "price": "$15.000"},
    {"name": "Comedero", "price": "$20.000"},
    {"name": "Bebedero", "price": "$18.000"},
    {"name": "Transportador", "price": "$95.000"}
]


@app.route("/")
def home():
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
        session["login_ok"] = True
        return redirect(url_for("mfa"))

    return render_template(
        "login.html",
        error="Usuario o contraseña incorrectos."
    )


@app.route("/mfa")
def mfa():

    if not session.get("login_ok"):
        return redirect(url_for("home"))

    return render_template("mfa.html")


@app.route("/verify", methods=["POST"])
def verify():

    if not session.get("login_ok"):
        return redirect(url_for("home"))

    otp = request.form.get("otp", "").strip()

    if not otp:
        return render_template(
            "mfa.html",
            error="Debe ingresar el código."
        )

    if totp.verify(otp):
        session["mfa_ok"] = True
        return redirect(url_for("products"))

    return render_template(
        "mfa.html",
        error="Código MFA inválido."
    )


@app.route("/products")
def products():

    if not session.get("mfa_ok"):
        return redirect(url_for("home"))

    return render_template(
        "products.html",
        products=PRODUCTS
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)