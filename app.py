import os
import io
import base64
import pyotp
import qrcode
from flask import Flask, render_template, request, redirect, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta-academica-petshop')

# Configuración Base de Datos Azure SQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///petshop.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Métricas Prometheus
LOGIN_SUCCESS_TOTAL = Counter('login_success_total', 'Total de logins exitosos')
LOGIN_FAIL_TOTAL = Counter('login_fail_total', 'Total de logins fallidos')

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    real_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    totp_secret = db.Column(db.String(32), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    qr_code_img = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        real_name = request.form.get('real_name')
        address = request.form.get('address')
        phone = request.form.get('phone')

        if not all([username, password, real_name, address, phone]):
            return render_template('signin.html', error="Todos los campos son obligatorios.", qr_code=None)

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('signin.html', error="El usuario ya existe.", qr_code=None)

        totp_secret = pyotp.random_base32()
        
        new_user = User(
            username=username,
            password=password,
            real_name=real_name,
            address=address,
            phone=phone,
            totp_secret=totp_secret
        )
        db.session.add(new_user)
        db.session.commit()

        # Generar QR para Google Authenticator
        totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
            name=username,
            issuer_name="PetShopCloud"
        )
        img = qrcode.make(totp_uri)
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_code_img = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return render_template('signin.html', success="Registro exitoso.", qr_code=qr_code_img)

    return render_template('signin.html', qr_code=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username, password=password).first()
        if not user:
            LOGIN_FAIL_TOTAL.inc()
            return render_template('login.html', error="Credenciales inválidas.")

        LOGIN_SUCCESS_TOTAL.inc()
        session['login_ok'] = True
        session['username'] = username
        return redirect(url_for('mfa'))

    return render_template('login.html')

@app.route('/mfa', methods=['GET'])
def mfa():
    if not session.get('login_ok'):
        return redirect(url_for('login'))
    return render_template('mfa.html')

@app.route('/verify', methods=['POST'])
def verify():
    if not session.get('login_ok'):
        return redirect(url_for('login'))

    otp_code = request.form.get('otp_code')
    username = session.get('username')
    user = User.query.filter_by(username=username).first()

    if user and pyotp.TOTP(user.totp_secret).verify(otp_code):
        session['mfa_ok'] = True
        return redirect(url_for('products'))

    return render_template('mfa.html', error="Código OTP incorrecto.")

@app.route('/products', methods=['GET'])
def products():
    if not session.get('login_ok') or not session.get('mfa_ok'):
        return redirect(url_for('login'))

    catalog = [
        {"name": "Alimento Premium Perros 15kg", "price": "$45.99"},
        {"name": "Arena para Gatos Aglutinante 10kg", "price": "$18.50"},
        {"name": "Juguete Mordedor Hueso de Goma", "price": "$8.99"},
        {"name": "Rascador para Gatos Multinivel", "price": "$55.00"},
        {"name": "Correa Retráctil 5 Metros", "price": "$14.25"},
        {"name": "Cama acolchada para Perros Medianos", "price": "$32.00"},
        {"name": "Shampoo Antipulgas Orgánico 500ml", "price": "$12.00"},
        {"name": "Snacks de Pollo deshidratado 250g", "price": "$7.50"},
        {"name": "Plato doble de Acero Inoxidable", "price": "$10.00"},
        {"name": "Transportadora rígida para Mascotas", "price": "$48.00"}
    ]
    return render_template('products.html', products=catalog)

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/metrics', methods=['GET'])
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)