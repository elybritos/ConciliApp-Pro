# -*- coding: utf-8 -*-
"""
database.py

Capa de base de datos para ConciliApp.
Usa SQLite localmente. Facilmente migrable a PostgreSQL.
"""

import sqlite3
import json
import hashlib
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "conciliapp.db")


def _get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inicializa las tablas de la base de datos."""
    with _get_connection() as conn:
        cursor = conn.cursor()

        # Tabla de usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nombre TEXT,
                email TEXT,
                activo INTEGER DEFAULT 1,
                creado_en TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de perfiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS perfiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                config_json TEXT NOT NULL,
                creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
                actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)

        # Tabla de conciliaciones (historial)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conciliaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                perfil_id INTEGER,
                nombre_archivo_banco TEXT,
                nombre_archivo_sistema TEXT,
                modo TEXT,
                total_registros INTEGER,
                conciliados INTEGER,
                pendientes INTEGER,
                sin_movimiento INTEGER,
                total_banco REAL,
                total_sistema REAL,
                ejecutada_en TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (perfil_id) REFERENCES perfiles(id)
            )
        """)

        conn.commit()

        # Crear usuario admin por defecto si no existe
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            crear_usuario("admin", "admin123", "Administrador", "admin@conciliapp.com")
            print("✅ Usuario admin creado: admin / admin123")


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def crear_usuario(username, password, nombre="", email=""):
    """Crea un nuevo usuario."""
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, email) VALUES (?, ?, ?, ?)",
                (username, _hash_password(password), nombre, email)
            )
            conn.commit()
            return True, "Usuario creado exitosamente"
    except sqlite3.IntegrityError:
        return False, "El nombre de usuario ya existe"


def validar_login(username, password):
    """Valida credenciales. Retorna (exito, user_id, nombre) o (False, None, None)."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, password_hash, nombre FROM usuarios WHERE username = ? AND activo = 1",
            (username,)
        )
        row = cursor.fetchone()
        if row and row["password_hash"] == _hash_password(password):
            return True, row["id"], row["nombre"]
        return False, None, None


def guardar_perfil(usuario_id, nombre, config_dict):
    """Guarda o actualiza un perfil."""
    config_json = json.dumps(config_dict, ensure_ascii=False)
    with _get_connection() as conn:
        cursor = conn.cursor()
        # Verificar si ya existe
        cursor.execute(
            "SELECT id FROM perfiles WHERE usuario_id = ? AND nombre = ?",
            (usuario_id, nombre)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE perfiles SET config_json = ?, actualizado_en = ? WHERE id = ?",
                (config_json, datetime.now().isoformat(), existing["id"])
            )
        else:
            cursor.execute(
                "INSERT INTO perfiles (usuario_id, nombre, config_json) VALUES (?, ?, ?)",
                (usuario_id, nombre, config_json)
            )
        conn.commit()
        return True


def listar_perfiles(usuario_id):
    """Lista todos los perfiles de un usuario."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, nombre, config_json, creado_en, actualizado_en FROM perfiles WHERE usuario_id = ? ORDER BY actualizado_en DESC",
            (usuario_id,)
        )
        rows = cursor.fetchall()
        return [{
            "id": r["id"],
            "nombre": r["nombre"],
            "config": json.loads(r["config_json"]),
            "creado_en": r["creado_en"],
            "actualizado_en": r["actualizado_en"]
        } for r in rows]


def eliminar_perfil(usuario_id, perfil_id):
    """Elimina un perfil."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM perfiles WHERE id = ? AND usuario_id = ?",
            (perfil_id, usuario_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def guardar_conciliacion(usuario_id, perfil_id, datos):
    """Guarda el resultado de una conciliacion en el historial."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conciliaciones 
            (usuario_id, perfil_id, nombre_archivo_banco, nombre_archivo_sistema, modo,
             total_registros, conciliados, pendientes, sin_movimiento, total_banco, total_sistema)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_id, perfil_id,
            datos.get("archivo_banco"), datos.get("archivo_sistema"),
            datos.get("modo"), datos.get("total"), datos.get("conciliados"),
            datos.get("pendientes"), datos.get("sin_movimiento"),
            datos.get("total_banco"), datos.get("total_sistema")
        ))
        conn.commit()


def obtener_historial(usuario_id, limite=50):
    """Obtiene el historial de conciliaciones."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, p.nombre as perfil_nombre 
            FROM conciliaciones c
            LEFT JOIN perfiles p ON c.perfil_id = p.id
            WHERE c.usuario_id = ?
            ORDER BY c.ejecutada_en DESC
            LIMIT ?
        """, (usuario_id, limite))
        return [dict(r) for r in cursor.fetchall()]


# Inicializar al importar
init_db()
