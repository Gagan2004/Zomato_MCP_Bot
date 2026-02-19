import sqlite3
import json
from datetime import datetime

DB_NAME = "orders.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cart_id TEXT,
            restaurant_id TEXT,
            items TEXT,
            status TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cart_id TEXT,
            user_id INTEGER NOT NULL,
            restaurant_id TEXT,
            items TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def log_cart_creation(user_id, cart_id, res_id, items):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    items_json = json.dumps(items)
    # Log to main orders table (for status tracking)
    cursor.execute('''
        INSERT INTO orders (user_id, cart_id, restaurant_id, items, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, cart_id, str(res_id), items_json, "cart_created"))
    
    # Also log to strictly separate carts table (historical record)
    cursor.execute('''
        INSERT INTO carts (user_id, cart_id, restaurant_id, items)
        VALUES (?, ?, ?, ?)
    ''', (user_id, cart_id, str(res_id), items_json))
    
    conn.commit()
    conn.close()

def update_order_status(cart_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE orders 
        SET status = ? 
        WHERE cart_id = ?
    ''', (status, cart_id))
    conn.commit()
    conn.close()

def get_user_orders(user_id, limit=5):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, restaurant_id, items, status, created_at 
        FROM orders 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    orders = []
    for row in rows:
        orders.append({
            "id": row[0],
            "res_id": row[1],
            "items": json.loads(row[2]) if row[2] else [],
            "status": row[3],
            "date": row[4]
        })
    return orders
