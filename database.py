# -*- coding: utf-8 -*-
"""
database.py
Capa de persistencia para ConciliApp.
"""

import sqlite3
import json

DB_FILE = "conciliapp.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS perfiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            modo TEXT,
            total_registros INTEGER,
            conciliados INTEGER,
            pendientes INTEGER,
            sin_movimiento INTEGER,
            total_banco REAL,
            total_sistema REAL,
            diferencia REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    c.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'admin', 'admin123')")
    conn.commit()
    conn.close()

def register_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return True, user_id
    except sqlite3.IntegrityError:
        conn.close()
        return False, None

def login_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1]}
    return None

def save_perfil(user_id, nombre, config):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM perfiles WHERE user_id = ? AND nombre = ?", (user_id, nombre))
    c.execute("INSERT INTO perfiles (user_id, nombre, config_json) VALUES (?, ?, ?)",
              (user_id, nombre, json.dumps(config, default=str)))
    conn.commit()
    conn.close()

def get_perfiles(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT nombre, config_json FROM perfiles WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return {nombre: json.loads(cfg) for nombre, cfg in rows}

def delete_perfil(user_id, nombre):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM perfiles WHERE user_id = ? AND nombre = ?", (user_id, nombre))
    conn.commit()
    conn.close()

def save_historial(user_id, modo, total, conc, pend, sin_mov, total_banco, total_sistema, diferencia):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO historial (user_id, modo, total_registros, conciliados, pendientes, sin_movimiento,
                               total_banco, total_sistema, diferencia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, modo, total, conc, pend, sin_mov, total_banco, total_sistema, diferencia))
    conn.commit()
    conn.close()

def get_historial(user_id, limit=20):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT modo, total_registros, conciliados, pendientes, sin_movimiento,
               total_banco, total_sistema, diferencia, created_at
        FROM historial WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows
