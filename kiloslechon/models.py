from database import get_db_connection

class User:
    def __init__(self, id, username, email, role):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        
    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, role FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['email'], row['role'])
        return None


class Order:
    def __init__(self, customer_id, item_type, details, fulfillment, schedule, total_amount, payment_status='Downpayment', order_status='Pending'):
        self.customer_id = customer_id
        self.item_type = item_type
        self.details = details
        self.fulfillment = fulfillment
        self.schedule = schedule
        self.total_amount = total_amount
        self.payment_status = payment_status
        self.order_status = order_status

    def save(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (customer_id, item_type, details, fulfillment_method, schedule_datetime, total_amount, payment_status, order_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (self.customer_id, self.item_type, self.details, self.fulfillment, self.schedule, self.total_amount, self.payment_status, self.order_status))
        conn.commit()
        last_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return last_id

    @staticmethod
    def update_status(order_id, new_status):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET order_status = %s WHERE id = %s", (new_status, order_id))
        conn.commit()
        cursor.close()
        conn.close()


class PigInventory:
    def __init__(self, pen_number, breed_type, weight_kg):
        self.pen_number = pen_number
        self.breed_type = breed_type
        self.weight_kg = weight_kg

    def save(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pig_inventory (pen_number, breed_type, weight_kg, status)
            VALUES (%s, %s, %s, 'In Pen')
        """, (self.pen_number, self.breed_type, self.weight_kg))
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def deduct_stock_for_order():
        """Awtomatikong binabawasan ang unang available na baboy sa pen kapag confirmed na ang order."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM pig_inventory WHERE status = 'In Pen' LIMIT 1")
        pig = cursor.fetchone()
        if pig:
            pig_id = pig['id']
            cursor.execute("UPDATE pig_inventory SET status = 'Reserved/Sold' WHERE id = %s", (pig_id,))
            conn.commit()
        cursor.close()
        conn.close()