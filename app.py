from flask import Flask,render_template,request,redirect,session
import pyotp
from prometheus_client import Counter,generate_latest

app = Flask(__name__)
app.secret_key='petshop-secret'

LOGIN_SUCCESS = Counter('login_success_total','Successful login')
LOGIN_FAIL = Counter('login_fail_total','Failed login')

USERNAME='admin'
PASSWORD='PetShop123'
TOTP_SECRET='JBSWY3DPEHPK3PXP'

products=[
 {'name':'Dog Food','price':'20 USD'},
 {'name':'Cat Food','price':'15 USD'},
 {'name':'Dog Toy','price':'8 USD'},
 {'name':'Cat Toy','price':'7 USD'},
 {'name':'Pet Shampoo','price':'12 USD'}
]

@app.route('/')
def home():
    session.clear()
    return render_template('login.html')

@app.route('/login',methods=['POST'])
def login():
    user=request.form.get('username')
    password=request.form.get('password')

    if user==USERNAME and password==PASSWORD:
        session['authenticated']=True
        return redirect('/mfa')

    LOGIN_FAIL.inc()
    return render_template(
        'login.html',
        error='Usuario o contraseña incorrectos'
    )

@app.route('/mfa')
def mfa():
    if not session.get('authenticated'):
        return redirect('/')

    return render_template('mfa.html')


@app.route('/verify',methods=['POST'])
def verify():
    code=request.form.get('code')
    totp=pyotp.TOTP(TOTP_SECRET)

    if totp.verify(code):
        session['mfa']=True
        LOGIN_SUCCESS.inc()
        return redirect('/products')

    LOGIN_FAIL.inc()
    return 'Invalid MFA code'

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

@app.route('/products')
def products_page():
    if not session.get('mfa'):
        return redirect('/')
    return render_template('products.html',products=products)

@app.route('/metrics')
def metrics():
    return generate_latest()

if __name__=='__main__':
    app.run()
