# app.py (only the important parts shown - integrate into your file)
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from models import db, Product, User, Order, OrderItem

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ---- Admin setup helper (create admin user if not exists) ----
def ensure_admin():
    with app.app_context():
        if not User.query.filter_by(username='admin').first():
            # set default admin password: kanak (you should change later)
            pw_hash = generate_password_hash('kanak')
            admin = User(username='admin', password=pw_hash)
            db.session.add(admin)
            db.session.commit()

# Call once at startup
with app.app_context():
    db.create_all()
    ensure_admin()

# ---- Checkout route that saves orders ----
@app.route('/checkout', methods=['GET','POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty')
        return redirect(url_for('index'))

    # calculate total
    total = 0.0
    items = []
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            subtotal = p.price * qty
            total += subtotal
            items.append((p, qty, p.price))

    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')

        # create order
        order = Order(user_id=session.get('user_id'), customer_name=name,
                      address=address, phone=phone, total_amount=total)
        db.session.add(order)
        db.session.flush()  # get order.id before commit

        # create order items
        for p, qty, price in items:
            oi = OrderItem(order_id=order.id, product_id=p.id, quantity=qty, price=price)
            db.session.add(oi)

        db.session.commit()
        session.pop('cart', None)
        flash(f'Order placed successfully. Order ID: {order.id}')
        return redirect(url_for('index'))

    # GET: show checkout page
    return render_template('checkout.html', total=total)

# ---- Admin panel now only accessible if logged in as admin user ----
@app.route('/admin-login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        u = User.query.filter_by(username=username).first()
        if u and check_password_hash(u.password, password):
            # set admin session flag
            session['is_admin'] = True
            flash('Admin logged in')
            return redirect(url_for('admin_panel'))
        flash('Invalid admin credentials')
    return render_template('admin_login.html')

@app.route('/admin-logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('Admin logged out')
    return redirect(url_for('index'))

# protect admin panel
@app.route('/admin', methods=['GET','POST'])
def admin_panel():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        # add product
        name = request.form.get('name')
        price = float(request.form.get('price') or 0)
        desc = request.form.get('description') or ''
        img = request.form.get('image') or ''
        p = Product(name=name, price=price, description=desc, image=img)
        db.session.add(p); db.session.commit()
        flash('Product added')
        return redirect(url_for('admin_panel'))
    products = Product.query.all()
    return render_template('admin.html', products=products)
