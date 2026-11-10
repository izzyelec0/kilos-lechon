import os
import csv
import zipfile
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import mysql.connector
from database import get_db_connection
from models import PigInventory

app = Flask(__name__)
app.secret_key = 'kiloslechon_secure_secret_key'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', name="Admin", role="Super Admin")

# --- ORDER MANAGEMENT ROUTES (OPTIMIZED & LOCK-FREE) ---
@app.route('/add-order', methods=['GET', 'POST'])
def add_order():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    edit_id = request.args.get('edit')
    order_to_edit = None

    if edit_id:
        cursor.execute("""
            SELECT o.*, c.name as customer_name, c.contact as customer_contact, c.gender as customer_gender, c.address as customer_address
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            WHERE o.id = %s
        """, (edit_id,))
        order_to_edit = cursor.fetchone()

    if request.method == 'POST':
        order_id_to_update = request.form.get('update_order_id')
        cust_name = request.form.get('customer_name').strip()
        contact = request.form.get('contact').strip()
        gender = request.form.get('gender', 'Male')
        address = request.form.get('address', '')

        item_type = request.form.get('order_item_type')
        details = request.form.get('details')
        fulfillment = request.form.get('fulfillment_type')
        schedule = request.form.get('selected-date')
        total_amount = float(request.form.get('total_price', 0))
        payment_status = request.form.get('pay-status', 'Downpayment')

        try:
            cursor.execute("SELECT id FROM customers WHERE LOWER(name) = %s OR contact = %s", (cust_name.lower(), contact))
            existing_cust = cursor.fetchone()

            if existing_cust:
                customer_id = existing_cust['id']
                cursor.execute("""
                    UPDATE customers 
                    SET name=%s, contact=%s, gender=%s, address=%s, is_deleted=0 
                    WHERE id=%s
                """, (cust_name, contact, gender, address, customer_id))
            else:
                cursor.execute("""
                    INSERT INTO customers (name, contact, gender, address) 
                    VALUES (%s, %s, %s, %s)
                """, (cust_name, contact, gender, address))
                customer_id = cursor.lastrowid

            if order_id_to_update:
                cursor.execute("""
                    UPDATE orders 
                    SET customer_id=%s, item_type=%s, details=%s, fulfillment_method=%s, 
                        schedule_datetime=%s, total_amount=%s, payment_status=%s
                    WHERE id=%s
                """, (customer_id, item_type, details, fulfillment, schedule, total_amount, payment_status, order_id_to_update))
                flash(f"Order #{order_id_to_update} ay matagumpay na na-update!", 'success')
            else:
                cursor.execute("""
                    INSERT INTO orders (customer_id, item_type, details, fulfillment_method, schedule_datetime, total_amount, payment_status, order_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
                """, (customer_id, item_type, details, fulfillment, schedule, total_amount, payment_status))
                flash('Ang bagong order ay matagumpay na naidagdag sa queue!', 'success')

            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f"Database Error: {str(e)}", 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('pending_orders'))

    cursor.execute("SELECT * FROM customers WHERE is_deleted = 0 ORDER BY name ASC")
    all_customers = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('add_order.html', customers=all_customers, edit_order=order_to_edit)

@app.route('/pending-orders')
def pending_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.*, c.name as customer_name, c.contact as customer_contact 
        FROM orders o 
        JOIN customers c ON o.customer_id = c.id 
        WHERE o.order_status = 'Pending' 
        ORDER BY o.id DESC
    """)
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('pending_order.html', orders=orders)

@app.route('/confirmed-orders')
def confirmed_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.*, c.name as customer_name, c.contact as customer_contact, c.address as customer_address 
        FROM orders o 
        JOIN customers c ON o.customer_id = c.id 
        WHERE o.order_status = 'Confirmed' 
        ORDER BY o.id DESC
    """)
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('confirmed_orders.html', orders=orders)

@app.route('/order/confirm/<int:order_id>', methods=['POST'])
def confirm_order_route(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET order_status = 'Confirmed' WHERE id = %s", (order_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    PigInventory.deduct_stock_for_order()
    flash(f"Order #{order_id} confirmed at nabawasan ang live inventory stock!", 'success')
    return redirect(url_for('pending_orders'))

@app.route('/order/archive/<int:order_id>', methods=['POST'])
def archive_order_route(order_id):
    reason = request.form.get('archive_reason', 'Walang binigay na dahilan')
    action_type = request.form.get('action_type', 'archive')
    
    status_target = 'Deleted' if action_type == 'delete' else 'Archived'

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders 
        SET order_status = %s, cancel_reason = %s, archived_at = NOW(), deleted_at = NOW() 
        WHERE id = %s
    """, (status_target, reason, order_id))
    conn.commit()
    cursor.close()
    conn.close()

    if status_target == 'Deleted':
        flash(f"Order #{order_id} ay inilipat sa Deletion Folder.", 'danger')
    else:
        flash(f"Order #{order_id} ay nai-archive!", 'info')
        
    return redirect(url_for('pending_orders'))

# --- CUSTOMER DIRECTORY ROUTES ---
@app.route('/customers')
def customers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT c.*, 
               COUNT(o.id) as total_orders, 
               COALESCE(SUM(o.total_amount), 0) as total_spent
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        WHERE c.is_deleted = 0
        GROUP BY c.id
        ORDER BY c.id DESC
    """)
    all_customers = cursor.fetchall()

    cursor.execute("""
        SELECT id, customer_id, item_type, details, schedule_datetime, total_amount, payment_status, order_status 
        FROM orders 
        ORDER BY id DESC
    """)
    all_orders = cursor.fetchall()

    orders_by_customer = {}
    for ord_item in all_orders:
        c_id = ord_item['customer_id']
        if c_id not in orders_by_customer:
            orders_by_customer[c_id] = []
        orders_by_customer[c_id].append(ord_item)

    for cust in all_customers:
        cust['orders'] = orders_by_customer.get(cust['id'], [])

    cursor.close()
    conn.close()
    return render_template('customers.html', customers=all_customers)

@app.route('/customer/edit/<int:customer_id>', methods=['POST'])
def edit_customer_route(customer_id):
    name = request.form.get('name').strip()
    contact = request.form.get('contact').strip()
    gender = request.form.get('gender')
    address = request.form.get('address')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE customers 
        SET name = %s, contact = %s, gender = %s, address = %s 
        WHERE id = %s
    """, (name, contact, gender, address, customer_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Impormasyon para kay customer #{customer_id} ay matagumpay na na-update!", 'success')
    return redirect(url_for('customers'))

@app.route('/customer/delete/<int:customer_id>', methods=['POST'])
def delete_customer_route(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE customers SET is_deleted = 1, deleted_at = NOW() WHERE id = %s", (customer_id,))
    cursor.execute("UPDATE orders SET order_status = 'Deleted', cancel_reason = 'Customer Profile Deleted', deleted_at = NOW() WHERE customer_id = %s", (customer_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Customer #{customer_id} ay nai-transfer na sa Deletion Folder.", 'danger')
    return redirect(url_for('customers'))

# --- PIG & PRODUCT INVENTORY CRUD ROUTES ---
@app.route('/inventory')
def inventory():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM inventory ORDER BY id DESC")
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventory.html', inventory=items)

@app.route('/inventory/add', methods=['POST'])
def add_inventory_item():
    item_name = request.form.get('item_name', '').strip()
    category = request.form.get('category', '').strip()
    classification = 'N/A' if category == 'Parts / Processed' else request.form.get('classification', 'Native').strip()
    estimated_kilos = float(request.form.get('estimated_kilos') or 0)
    pen_number = request.form.get('pen_number', '').strip()
    status = request.form.get('status', 'Available')
    reserved_customer = request.form.get('reserved_customer', '').strip() if status == 'Reserved' else None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO inventory (item_name, category, classification, estimated_kilos, pen_number, status, reserved_customer)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (item_name, category, classification, estimated_kilos, pen_number, status, reserved_customer))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Matagumpay na naidagdag ang item sa inventory!', 'success')
    return redirect(url_for('inventory'))

@app.route('/inventory/edit/<int:item_id>', methods=['POST'])
def edit_inventory_item(item_id):
    item_name = request.form.get('item_name', '').strip()
    category = request.form.get('category', '').strip()
    classification = 'N/A' if category == 'Parts / Processed' else request.form.get('classification', 'Native').strip()
    estimated_kilos = float(request.form.get('estimated_kilos') or 0)
    pen_number = request.form.get('pen_number', '').strip()
    status = request.form.get('status', 'Available')
    reserved_customer = request.form.get('reserved_customer', '').strip() if status == 'Reserved' else None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE inventory 
        SET item_name = %s, category = %s, classification = %s, estimated_kilos = %s, pen_number = %s, status = %s, reserved_customer = %s
        WHERE id = %s
    """, (item_name, category, classification, estimated_kilos, pen_number, status, reserved_customer, item_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Item #{item_id} ay matagumpay na na-update!", 'success')
    return redirect(url_for('inventory'))

@app.route('/inventory/delete/<int:item_id>', methods=['POST'])
def delete_inventory_item(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE id = %s", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"Item #{item_id} ay matagumpay na natanggal sa inventory.", 'danger')
    return redirect(url_for('inventory'))

# --- CALENDAR & SALES ROUTES ---
@app.route('/calendar')
def calendar_view():
    return render_template('calendar_view.html')

@app.route('/sales')
def sales():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            COUNT(id) as total_orders,
            COALESCE(SUM(total_amount), 0) as total_revenue,
            COALESCE(AVG(total_amount), 0) as avg_order_value
        FROM orders
        WHERE order_status NOT IN ('Archived', 'Deleted')
    """)
    stats = cursor.fetchone()

    cursor.execute("""
        SELECT 
            DATE_FORMAT(schedule_datetime, '%Y-%m') as month_str,
            COALESCE(SUM(total_amount), 0) as monthly_revenue
        FROM orders
        WHERE order_status NOT IN ('Archived', 'Deleted') AND schedule_datetime IS NOT NULL
        GROUP BY month_str
        ORDER BY month_str ASC
    """)
    monthly_data = cursor.fetchall()

    cursor.execute("""
        SELECT 
            DATE_FORMAT(schedule_datetime, '%Y') as year_str,
            COALESCE(SUM(total_amount), 0) as yearly_revenue
        FROM orders
        WHERE order_status NOT IN ('Archived', 'Deleted') AND schedule_datetime IS NOT NULL
        GROUP BY year_str
        ORDER BY year_str ASC
    """)
    yearly_data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('sales.html', 
                           stats=stats, 
                           monthly_data=monthly_data, 
                           yearly_data=yearly_data)

# --- ARCHIVE & FOLDERS ROUTE ---
@app.route('/archive')
def archive():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT o.*, c.name as customer_name, c.contact as customer_contact, c.address as customer_address,
               DATE_FORMAT(COALESCE(o.deleted_at, o.archived_at, NOW()), '%Y-%m-%d %H:%i') as formatted_deleted_date
        FROM orders o 
        JOIN customers c ON o.customer_id = c.id 
        WHERE o.order_status IN ('Archived', 'Deleted')
        ORDER BY o.id DESC
    """)
    archived_orders = cursor.fetchall()

    cursor.execute("""
        SELECT id, name, contact, address, gender, 
               DATE_FORMAT(COALESCE(deleted_at, NOW()), '%Y-%m-%d %H:%i') as formatted_deleted_date
        FROM customers
        WHERE is_deleted = 1
        ORDER BY id DESC
    """)
    deleted_customers = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return render_template('archived_list.html', 
                           archived_orders=archived_orders,
                           deleted_customers=deleted_customers)

@app.route('/order/restore/<int:order_id>', methods=['POST'])
def restore_order_route(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET order_status = 'Pending', archived_at = NULL, deleted_at = NULL WHERE id = %s", (order_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash(f"Order #{order_id} ay na-restore pabalik sa Queue!", 'success')
    return redirect(url_for('archive'))

@app.route('/customer/restore/<int:customer_id>', methods=['POST'])
def restore_customer_route(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE customers SET is_deleted = 0, deleted_at = NULL WHERE id = %s", (customer_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash(f"Customer #{customer_id} profile restored!", 'success')
    return redirect(url_for('archive'))
@app.route('/logout')
def logout():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)