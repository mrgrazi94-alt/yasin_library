import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = 'yasin_library_secret_key'

# تحديد مسار قاعدة البيانات في مجلد tmp
db_path = os.path.join('/tmp', 'library.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# إنشاء الجداول عند بدء تشغيل التطبيق
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print("DB Error:", e)

ADMIN_PASSWORD = "123"

# جدول المنتجات
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(200), nullable=False, default='default.jpg')

# جدول الطلبات (التوصيل)
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(250), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='قيد المعالجة')
    items_summary = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

# ==========================================
# مسارات الموقع الإلكتروني (الويب)
# ==========================================

@app.route('/')
def index():
    search_query = request.args.get('q', '').strip()
    if search_query:
        products = Product.query.filter(
            (Product.name.contains(search_query)) | 
            (Product.category.contains(search_query))
        ).all()
    else:
        products = Product.query.all()
    return render_template('index.html', products=products, search_query=search_query)

@app.route('/add-to-cart/<int:product_id>')
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    str_id = str(product_id)
    
    if str_id in cart:
        cart[str_id]['quantity'] += 1
    else:
        cart[str_id] = {
            'name': product.name,
            'price': product.price,
            'image': product.image,
            'quantity': 1
        }
    session.modified = True
    return redirect(url_for('index'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    return render_template('cart.html', cart=cart, total=total)

@app.route('/remove-from-cart/<string:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    if product_id in cart:
        del cart[product_id]
        session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('index'))
        
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        notes = request.form.get('notes')
        
        summary_parts = [f"{item['name']} (العدد: {item['quantity']})" for item in cart.values()]
        items_summary = " - ".join(summary_parts)
        
        new_order = Order(
            customer_name=name,
            phone=phone,
            address=address,
            notes=notes,
            total_price=total,
            items_summary=items_summary
        )
        db.session.add(new_order)
        db.session.commit()
        
        session.pop('cart', None)
        return render_template('order_success.html')
        
    return render_template('checkout.html', total=total)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged'] = True
            return redirect(url_for('admin'))
        else:
            flash('كلمة المرور غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin_logged'):
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category', 'كتب')
        
        image = request.files.get('image')
        filename = 'logo.jpg'
        
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            # ⭐ استخدمنا BASE_DIR هنا
            image.save(os.path.join(BASE_DIR, 'static', filename))
            
        new_product = Product(name=name, price=price, category=category, image=filename)
        db.session.add(new_product)
        db.session.commit()
        
        return redirect(url_for('admin'))
        
    products = Product.query.all()
    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin.html', products=products, orders=orders)

@app.route('/order-done/<int:id>')
def order_done(id):
    if not session.get('admin_logged'):
        return redirect(url_for('login'))
    order = Order.query.get_or_404(id)
    order.status = 'تم التوصيل'
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('admin_logged', None)
    return redirect(url_for('index'))

@app.route('/add', methods=['POST'])
def add_product():
    if not session.get('admin_logged'):
        return redirect(url_for('login'))
    
    name = request.form.get('name')
    category = request.form.get('category')
    price = request.form.get('price')
    
    image_file = request.files.get('image')
    image_filename = 'default.jpg'
    
    if image_file and image_file.filename != '':
        ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else 'jpg'
        image_filename = f"{uuid.uuid4().hex}.{ext}"
        # ⭐ استخدمنا BASE_DIR هنا
        image_file.save(os.path.join(BASE_DIR, 'static', image_filename))

    new_product = Product(name=name, category=category, price=float(price), image=image_filename)
    db.session.add(new_product)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/delete/<int:id>')
def delete_product(id):
    if not session.get('admin_logged'):
        return redirect(url_for('login'))
    product = Product.query.get_or_404(id)
    if product.image != 'default.jpg':
        # ⭐ استخدمنا BASE_DIR هنا
        path = os.path.join(BASE_DIR, 'static', product.image)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if not session.get('admin_logged'):
        return redirect(url_for('login'))
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.category = request.form.get('category')
        product.price = float(request.form.get('price'))
        
        image_file = request.files.get('image')
        if image_file and image_file.filename != '':
            if product.image != 'default.jpg':
                # ⭐ استخدمنا BASE_DIR هنا
                old = os.path.join(BASE_DIR, 'static', product.image)
                if os.path.exists(old):
                    os.remove(old)
            ext = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else 'jpg'
            image_filename = f"{uuid.uuid4().hex}.{ext}"
            image_file.save(os.path.join(BASE_DIR, 'static', image_filename))
            product.image = image_filename
            
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('edit.html', product=product)

# ==========================================
# مسارات تطبيق الموبايل (API) - Flutter
# ==========================================

@app.route('/api/products', methods=['GET'])
def api_get_products():
    search_query = request.args.get('q', '').strip()
    if search_query:
        products = Product.query.filter(
            (Product.name.contains(search_query)) | 
            (Product.category.contains(search_query))
        ).all()
    else:
        products = Product.query.all()
        
    products_list = []
    for p in products:
        products_list.append({
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'price': p.price,
            'image': request.host_url + 'static/' + p.image
        })
    return jsonify({'status': 'success', 'data': products_list})

@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    data = request.get_json()
    print("📦 البيانات المستلمة من الزبون:")
    print(data)
    
    if not data:
        return jsonify({'status': 'error', 'message': 'لا توجد بيانات'}), 400
        
    try:
        new_order = Order(
            customer_name=data.get('name'),
            phone=data.get('phone'),
            address=data.get('address'),
            notes=data.get('notes', ''),
            total_price=data.get('total_price'),
            items_summary=data.get('items_summary')
        )
        db.session.add(new_order)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'تم إرسال الطلب بنجاح'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

app = app

if __name__ == '__main__':
    app.run(debug=True)