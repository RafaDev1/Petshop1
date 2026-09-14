import os
import pyotp
import qrcode
import io
from flask import Flask, request, render_template, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# SQLAlchemy Config (SQLAlchemy 2.x compatible)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Prometheus Metrics (definidas una sola vez)
login_success_total = Counter('login_success_total', 'Total logins successful')
login_fail_total = Counter('login_fail_total', 'Total logins failed')

# User Model (SQLAlchemy 2.x)
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    real_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    totp_secret = db.Column(db.String(100), nullable=False)

# Registro de usuario
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        real_name = request.form['real_name']
        address = request.form['address']
        phone = request.form['phone']

        # Nueva sintaxis SQLAlchemy 2.x
        existing_user = db.session