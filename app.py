# app.py — cleaned, deduplicated, safer
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import time

# import models (make sure models.py is present and correct)
from models import db, Product, User, Order, OrderItem

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload settings
UPLOAD_FOLDER = os.path.join('static', 'image')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

# ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# initialize db
db.init_app(app)

# ---- Helper: ensure admin user exists ----
def ensure_admin():
    """
    Creates DB tables and a default admin user if none exists.
    IMPORTANT: change default admin password after first login or set SECRET_ADMIN_PASSWORD env var.
    """
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            default_pw = os.environ.get('DEFAULT_ADMIN_PW', 'kanak')
            pw_hash = generate_password_hash(default_pw)
            admin = User(username='admin', password=pw_hash)
            db.session.add(admin)
            db.session.commit()

# Call once now to create tables & admin
ensure_admin()

# ---------------- Routes ----------------

@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/product/<int:pid>')
def product(pid):
    p = Product.query.get_or_404(pid)
    return render_template('product.html', p=p)

@app.route('/add_to_cart/<int:pid>')
def add_to_cart(pid):
    cart = session.get('cart', {})
    cart[str(pid)] = cart.get(str(pid), 0) + 1
    session['cart'] = cart
    flash('Item added to cart')
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    items = []
    total = 0.0
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            subtotal = p.price * qty
            items.append({'product': p, 'qty': qty, 'subtotal': subtotal})
            total += subtotal
    return render_template('cart.html', items=items, total=total)

@app.route('/remove_from_cart/<int:pid>')
def remove_from_cart(pid):
    cart = session.get('cart', {})
    cart.pop(str(pid), None)
    session['cart'] = cart
    flash('Item removed from cart')
    return redirect(url_for('cart'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    """
    POST params:
      pid: product id (string or int)
      action: 'inc' | 'dec' | 'set' | 'remove'
      qty: used when action=='set' (integer)
    """
    pid = str(request.form.get('pid') or "")
    action = request.form.get('action') or ""
    cart = session.get('cart', {})

    if not pid:
        flash("Invalid product.")
        return redirect(url_for('cart'))

    if action == 'inc':
        cart[pid] = cart.get(pid, 0) + 1
    elif action == 'dec':
        if cart.get(pid, 0) > 1:
            cart[pid] = cart.get(pid, 0) - 1
        else:
            # if qty becomes 0 or 1->dec, remove item
            cart.pop(pid, None)
    elif action == 'set':
        try:
            q = int(request.form.get('qty') or 0)
            if q > 0:
                cart[pid] = q
            else:
                cart.pop(pid, None)
        except ValueError:
            flash("Enter a valid quantity.")
    elif action == 'remove':
        cart.pop(pid, None)
    else:
        flash("Unknown action.")

    session['cart'] = cart
    return redirect(url_for('cart'))

# ----- User auth (basic) -----
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if User.query.filter_by(username=uname).first():
            flash('Username already taken'); return redirect(url_for('register'))
        u = User(username=uname, password=generate_password_hash(pwd))
        db.session.add(u); db.session.commit()
        flash('Registered. Please login.'); return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']; pwd = request.form['password']
        u = User.query.filter_by(username=uname).first()
        if u and check_password_hash(u.password, pwd):
            session['user_id'] = u.id
            session['username'] = u.username
            flash('Logged in'); return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Logged out'); return redirect(url_for('index'))

# ----- Admin login & panel -----
@app.route('/admin-login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username'); password = request.form.get('password')
        u = User.query.filter_by(username=username).first()
        if u and check_password_hash(u.password, password):
            # For safety, tie admin session to user id (not only a flag)
            session['is_admin'] = True
            session['admin_user_id'] = u.id
            flash('Admin logged in'); return redirect(url_for('admin_panel'))
        flash('Invalid admin credentials')
    return render_template('admin_login.html')

@app.route('/admin-logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_user_id', None)
    flash('Admin logged out'); return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # read form fields safely
        name = (request.form.get('name') or '').strip()
        price_raw = (request.form.get('price') or '').strip()
        desc = (request.form.get('description') or '').strip()
        file = request.files.get('image_file')  # file input

        # validation
        if not name:
            flash('Product name is required.')
            return redirect(url_for('admin_panel'))
        try:
            price = float(price_raw) if price_raw != "" else 0.0
            if price < 0:
                raise ValueError()
        except Exception:
            flash('Enter a valid non-negative price.')
            return redirect(url_for('admin_panel'))

        # handle upload
        img_filename = ''
        if file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    file.save(save_path)
                    img_filename = filename
                except Exception as e:
                    flash('Failed to save uploaded image: ' + str(e))
                    return redirect(url_for('admin_panel'))
            else:
                flash('Invalid image type. Allowed: png, jpg, jpeg, gif.')
                return redirect(url_for('admin_panel'))

        # final image value: uploaded file wins, else text input
        image_field = img_filename or (request.form.get('image') or '').strip()

        # save product
        p = Product(name=name, price=price, description=desc, image=image_field)
        db.session.add(p)
        try:
            db.session.commit()
            flash('Product added successfully.')
        except Exception as e:
            db.session.rollback()
            flash('Error saving product: ' + str(e))

        return redirect(url_for('admin_panel'))

    # GET -> show admin page (list products)
    products = Product.query.all()
    return render_template('admin.html', products=products)

# Admin: view all orders
@app.route('/admin/orders')
def admin_orders():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)

# Admin: view single order details
@app.route('/admin/order/<int:order_id>')
def admin_order_detail(order_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    order = Order.query.get_or_404(order_id)
    items = OrderItem.query.filter_by(order_id=order.id).all()
    return render_template('admin_order_detail.html', order=order, items=items)

# ----- Edit product (GET shows form, POST saves changes) -----
@app.route('/admin/product/edit/<int:pid>', methods=['GET','POST'])
def admin_edit_product(pid):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    p = Product.query.get_or_404(pid)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        price_raw = (request.form.get('price') or '').strip()
        desc = (request.form.get('description') or '').strip()
        img = (request.form.get('image') or '').strip()

        if not name:
            flash('Product name required.')
            return redirect(url_for('admin_edit_product', pid=pid))

        try:
            price = float(price_raw) if price_raw != "" else 0.0
            if price < 0: raise ValueError()
        except Exception:
            flash('Enter a valid non-negative price.')
            return redirect(url_for('admin_edit_product', pid=pid))

        p.name = name
        p.price = price
        p.description = desc
        p.image = img
        try:
            db.session.commit()
            flash('Product updated.')
        except Exception as e:
            db.session.rollback()
            flash('Error updating product: ' + str(e))
        return redirect(url_for('admin_panel'))

    # GET -> show edit form
    return render_template('admin_edit_product.html', p=p)

# ----- Delete product (POST recommended) -----
@app.route('/admin/product/delete/<int:pid>', methods=['POST'])
def admin_delete_product(pid):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    p = Product.query.get_or_404(pid)
    try:
        db.session.delete(p)
        db.session.commit()
        flash('Product deleted.')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting product: ' + str(e))
    return redirect(url_for('admin_panel'))

@app.route('/checkout', methods=['GET','POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty')
        return redirect(url_for('index'))

    total = 0
    items = []
    for pid, qty in cart.items():
        p = Product.query.get(int(pid))
        if p:
            subtotal = p.price * qty
            total += subtotal
            items.append((p, qty, p.price))

    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        phone = request.form['phone']

        order = Order(
            user_id=session.get("user_id"),
            customer_name=name,
            address=address,
            phone=phone,
            total_amount=total
        )
        db.session.add(order)
        db.session.flush()

        for p, qty, price in items:
            oi = OrderItem(order_id=order.id, product_id=p.id, quantity=qty, price=price)
            db.session.add(oi)

        db.session.commit()
        session['cart'] = {}

        return redirect(url_for('order_success', order_id=order.id))

    return render_template('checkout.html', items=items, total=total)

@app.route('/order-success/<int:order_id>')
def order_success(order_id):
    return render_template('order_success.html', order_id=order_id)

@app.route('/debug-products')
def debug_products():
    products = Product.query.all()
    out = []
    for p in products:
        out.append({
            'id': p.id,
            'name': p.name,
            'price': float(p.price) if p.price is not None else None,
            'desc': p.description,
            'image': p.image
        })
    return {"products": out}


# ----- run server -----
if __name__ == '__main__':
    print("Starting Flask app on http://127.0.0.1:5000")
    app.run(debug=True)
