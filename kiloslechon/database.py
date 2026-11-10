import mysql.connector

# XAMPP MySQL Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'kiloslechon_db'
}

def get_db_connection():
    """Gumagawa at nagbabalik ng koneksyon sa XAMPP MySQL database."""
    conn = mysql.connector.connect(**db_config)
    return conn