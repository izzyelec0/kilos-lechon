CREATE DATABASE IF NOT EXISTS kiloslechon_db;
USE kiloslechon_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'Admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    contact VARCHAR(20) NOT NULL,
    gender VARCHAR(20) NULL,
    address TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    item_type VARCHAR(100) NOT NULL,
    details TEXT NOT NULL,
    fulfillment_method VARCHAR(50) NOT NULL,
    schedule_datetime VARCHAR(100) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    payment_status VARCHAR(50) DEFAULT 'Downpayment',
    order_status VARCHAR(50) DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    classification VARCHAR(50) NOT NULL,
    estimated_kilos DECIMAL(5,2) NOT NULL,
    pen_number VARCHAR(50),
    status VARCHAR(50) DEFAULT 'Available'
);


INSERT INTO users (username, password, email, role) VALUES 
('lapitan_admin', 'admin123', 'kiloslechonsystem@gmail.com', 'Admin'),
('lapitan_owner', 'owner123', 'lapitan.lechon.lb@gmail.com', 'Super Admin');

INSERT INTO customers (name, contact, gender, address) VALUES 
('Juan Dela Cruz', '0917-123-4567', 'Male', 'Brgy. Batong Malake, Los Baños'),
('Maria Santos', '0918-987-6543', 'Female', 'Brgy. San Antonio, Los Baños');

ALTER TABLE inventory ADD COLUMN reserved_customer VARCHAR(100) DEFAULT NULL AFTER status;

ALTER TABLE orders 
ADD COLUMN cancel_reason VARCHAR(255) DEFAULT NULL,
ADD COLUMN archived_at DATETIME DEFAULT NULL;

ALTER TABLE orders MODIFY COLUMN order_status VARCHAR(50) DEFAULT 'Pending';

ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS deleted_at DATETIME DEFAULT NULL,
ADD COLUMN IF NOT EXISTS cancel_reason VARCHAR(255) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS archived_at DATETIME DEFAULT NULL;

ALTER TABLE customers 
ADD COLUMN IF NOT EXISTS is_deleted TINYINT(1) DEFAULT 0,
ADD COLUMN IF NOT EXISTS deleted_at DATETIME DEFAULT NULL;