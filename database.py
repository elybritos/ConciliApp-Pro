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

DB_PATH = os.path.join(os.path.dirname(__file__), "conciliapp.db")


def _get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inicializa las tablas de la base de datos."""
    with _get_connection() as conn:
        cursor = conn.cursor()

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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pendientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                concepto_banco TEXT,
                importe_banco REAL,
                fecha TEXT,
                concepto_sistema TEXT,
                importe_sistema REAL,
                estado TEXT DEFAULT 'PENDIENTE',
                periodo TEXT,
                creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
                resuelto_en TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_empresa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL UNIQUE,
                nombre_empresa TEXT DEFAULT 'ConciliApp PRO',
                logo_url TEXT DEFAULT '',
                color_primario TEXT DEFAULT '#1e40af',
                color_secundario TEXT DEFAULT '#64748b',
                color_exito TEXT DEFAULT '#11998e',
                color_alerta TEXT DEFAULT '#f5576c',
                modo_oscuro INTEGER DEFAULT 0,
                alerta_diferencia REAL DEFAULT 100.0,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        """)

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            crear_usuario("admin", "admin123", "Administrador", "admin@conciliapp.com")
            print("Usuario admin creado: admin / admin123")


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def crear_usuario(username, password, nombre="", email=""):
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (username, password_hash, nombre, email) VALUES (?, ?, ?, ?)",
                (username, _hash_password(password), nombre, email)
            )
            uid = cursor.lastrowid
            cursor.execute(
                "INSERT INTO config_empresa (usuario_id) VALUES (?)",
                (uid,)
            )
            conn.commit()
            return True, "Usuario creado exitosamente"
    except sqlite3.IntegrityError:
        return False, "El nombre de usuario ya existe"


def validar_login(username, password):
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
    config_json = json.dumps(config_dict, ensure_ascii=False)
    with _get_connection() as conn:
        cursor = conn.cursor()
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
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM perfiles WHERE id = ? AND usuario_id = ?",
            (perfil_id, usuario_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def guardar_conciliacion(usuario_id, perfil_id, datos):
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


# ═══════════════════════════════════════════════════════════════════════
# PENDIENTES (PASO 5)
# ═══════════════════════════════════════════════════════════════════════

def guardar_pendientes(usuario_id, df_pendientes, periodo):
    """Guarda los pendientes de una conciliacion para arrastrar al siguiente periodo."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        for _, row in df_pendientes.iterrows():
            fecha_val = row.get('Fecha')
            fecha_str = str(fecha_val)[:10] if fecha_val is not None and str(fecha_val) not in ['NaT', 'nan', 'None', ''] else None

            concepto_sis = row.get('Concepto_Sistema')
            concepto_sis_str = str(concepto_sis) if concepto_sis is not None and str(concepto_sis) not in ['nan', 'None', ''] else None

            importe_sis = row.get('Importe_Sistema')
            importe_sis_val = float(importe_sis) if importe_sis is not None and str(importe_sis) not in ['nan', 'None', ''] else None

            cursor.execute("""
                INSERT INTO pendientes (usuario_id, concepto_banco, importe_banco, fecha,
                                        concepto_sistema, importe_sistema, estado, periodo)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDIENTE', ?)
            """, (
                usuario_id,
                str(row.get('Concepto_Banco', '')),
                float(row.get('Importe_Banco', 0) or 0),
                fecha_str,
                concepto_sis_str,
                importe_sis_val,
                periodo
            ))
        conn.commit()


def obtener_pendientes(usuario_id, estado='PENDIENTE'):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM pendientes 
            WHERE usuario_id = ? AND estado = ?
            ORDER BY creado_en DESC
        """, (usuario_id, estado))
        return [dict(r) for r in cursor.fetchall()]


def resolver_pendiente(pendiente_id, usuario_id):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pendientes SET estado = 'RESUELTO', resuelto_en = ?
            WHERE id = ? AND usuario_id = ?
        """, (datetime.now().isoformat(), pendiente_id, usuario_id))
        conn.commit()
        return cursor.rowcount > 0


def contar_pendientes(usuario_id):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM pendientes WHERE usuario_id = ? AND estado = 'PENDIENTE'",
            (usuario_id,)
        )
        return cursor.fetchone()[0]


# ═══════════════════════════════════════════════════════════════════════
# CONFIG EMPRESA
# ═══════════════════════════════════════════════════════════════════════

def obtener_config_empresa(usuario_id):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM config_empresa WHERE usuario_id = ?",
            (usuario_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        cursor.execute(
            "INSERT INTO config_empresa (usuario_id) VALUES (?)",
            (usuario_id,)
        )
        conn.commit()
        cursor.execute(
            "SELECT * FROM config_empresa WHERE usuario_id = ?",
            (usuario_id,)
        )
        return dict(cursor.fetchone())


def guardar_config_empresa(usuario_id, config):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE config_empresa SET
                nombre_empresa = ?,
                logo_url = ?,
                color_primario = ?,
                color_secundario = ?,
                color_exito = ?,
                color_alerta = ?,
                modo_oscuro = ?,
                alerta_diferencia = ?
            WHERE usuario_id = ?
        """, (
            config.get('nombre_empresa', 'ConciliApp PRO'),
            config.get('logo_url', ''),
            config.get('color_primario', '#1e40af'),
            config.get('color_secundario', '#64748b'),
            config.get('color_exito', '#11998e'),
            config.get('color_alerta', '#f5576c'),
            config.get('modo_oscuro', 0),
            config.get('alerta_diferencia', 100.0),
            usuario_id
        ))
        conn.commit()
        return True


init_db()
