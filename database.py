# -*- coding: utf-8 -*-
"""
ConciliApp PRO v2.0 — Conciliacion Bancaria con Modo Oscuro, 
Deteccion de Banco, Alertas, Pendientes Arrastrables y Personalizacion.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
import os
import sys
import importlib.util

# ═══════════════════════════════════════════════════════════════════════
# CARGA DIRECTA DE MODULOS (fix para Streamlit Cloud)
# ═══════════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cargar motor_conciliacion.py
motor_path = os.path.join(BASE_DIR, "motor_conciliacion.py")
if os.path.exists(motor_path):
    spec_motor = importlib.util.spec_from_file_location("motor_conciliacion", motor_path)
    motor = importlib.util.module_from_spec(spec_motor)
    spec_motor.loader.exec_module(motor)
    leer_archivo = motor.leer_archivo
    detectar_fila_encabezado = motor.detectar_fila_encabezado
    detectar_columnas_recomendadas = motor.detectar_columnas_recomendadas
    diagnosticar_columna = motor.diagnosticar_columna
    conciliar = motor.conciliar
    conciliar_agregado = motor.conciliar_agregado
    detectar_banco = motor.detectar_banco
else:
    st.error(f"No se encuentra motor_conciliacion.py")
    st.stop()

# Cargar database.py
db_path = os.path.join(BASE_DIR, "database.py")
if os.path.exists(db_path):
    spec_db = importlib.util.spec_from_file_location("database", db_path)
    db = importlib.util.module_from_spec(spec_db)
    spec_db.loader.exec_module(db)
    crear_usuario = db.crear_usuario
    validar_login = db.validar_login
    guardar_perfil = db.guardar_perfil
    listar_perfiles = db.listar_perfiles
    eliminar_perfil = db.eliminar_perfil
    guardar_conciliacion = db.guardar_conciliacion
    obtener_historial = db.obtener_historial
    guardar_pendientes = db.guardar_pendientes
    obtener_pendientes = db.obtener_pendientes
    resolver_pendiente = db.resolver_pendiente
    contar_pendientes = db.contar_pendientes
    obtener_config_empresa = db.obtener_config_empresa
    guardar_config_empresa = db.guardar_config_empresa
else:
    st.error(f"No se encuentra database.py")
    st.stop()

# ── Estado de sesion ─────────────────────────────────────────────────────
for key, default in [
    ("user_id", None), ("user_name", None), ("page", "login"),
    ("resultado", None), ("modo", None), ("dark_mode", False),
    ("perfil_a_usar", None)
]:
    if key not in st.session_state:
        st.session_state[key] = default

def logout():
    for key in ["user_id", "user_name", "page", "resultado", "modo", "perfil_a_usar"]:
        st.session_state[key] = None if key != "page" else "login"
    st.rerun()

def go_to(page):
    st.session_state["page"] = page
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURACION DE EMPRESA + MODO OSCURO
# ═══════════════════════════════════════════════════════════════════════

def get_empresa_config():
    if st.session_state["user_id"]:
        return obtener_config_empresa(st.session_state["user_id"])
    return {
        'nombre_empresa': 'ConciliApp PRO',
        'logo_url': '',
        'color_primario': '#1e40af',
        'color_secundario': '#64748b',
        'color_exito': '#11998e',
        'color_alerta': '#f5576c',
        'modo_oscuro': 0,
        'alerta_diferencia': 100.0
    }

# Detectar modo oscuro
emp_cfg = get_empresa_config()
is_dark = st.session_state.get("dark_mode", bool(emp_cfg.get("modo_oscuro", 0)))

# Colores segun modo
if is_dark:
    bg_color = "#0f172a"
    text_color = "#f1f5f9"
    card_bg = "#1e293b"
    card_border = "#334155"
    input_bg = "#1e293b"
    sidebar_bg = "#0f172a"
else:
    bg_color = "#ffffff"
    text_color = "#1e293b"
    card_bg = "#f8fafc"
    card_border = "#e2e8f0"
    input_bg = "#ffffff"
    sidebar_bg = "#f8fafc"

# ── Estilos dinamicos ────────────────────────────────────────────────────
st.set_page_config(
    page_title=emp_cfg.get('nombre_empresa', 'ConciliApp PRO'),
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed" if st.session_state["user_id"] is None else "expanded",
)

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background-color: {bg_color} !important; }}
    .main-header {{ font-size: 2.8rem; font-weight: 700; color: {emp_cfg.get('color_primario', '#1e40af')}; margin-bottom: 0.2rem; }}
    .sub-header {{ font-size: 1.1rem; color: {emp_cfg.get('color_secundario', '#64748b')}; margin-bottom: 2rem; }}
    .login-box {{ max-width: 400px; margin: 0 auto; padding: 2rem; background: {card_bg}; border-radius: 16px; border: 1px solid {card_border}; }}
    .metric-box {{
        background: linear-gradient(135deg, {emp_cfg.get('color_primario', '#1e40af')} 0%, #764ba2 100%);
        border-radius: 16px; padding: 1.2rem; color: white;
        text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }}
    .metric-box.green {{ background: linear-gradient(135deg, {emp_cfg.get('color_exito', '#11998e')} 0%, #38ef7d 100%); }}
    .metric-box.orange {{ background: linear-gradient(135deg, #f093fb 0%, {emp_cfg.get('color_alerta', '#f5576c')} 100%); }}
    .metric-box.blue {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }}
    .metric-value {{ font-size: 2.2rem; font-weight: 700; margin: 0; }}
    .metric-label {{ font-size: 0.9rem; opacity: 0.9; margin-top: 0.3rem; }}
    .perfil-card {{
        background: {card_bg}; border: 1px solid {card_border}; border-radius: 12px;
        padding: 1.2rem; margin-bottom: 0.8rem; transition: all 0.2s;
    }}
    .perfil-card:hover {{ border-color: {emp_cfg.get('color_primario', '#1e40af')}; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
    .diag-ok {{ color: {emp_cfg.get('color_exito', '#059669')}; font-weight: 600; }}
    .diag-warn {{ color: #d97706; font-weight: 600; }}
    .diag-error {{ color: {emp_cfg.get('color_alerta', '#dc2626')}; font-weight: 600; }}
    .alerta-box {{
        background: linear-gradient(135deg, {emp_cfg.get('color_alerta', '#f5576c')} 0%, #ff6b6b 100%);
        border-radius: 12px; padding: 1rem; color: white; margin: 1rem 0;
        text-align: center; font-weight: 600;
    }}
    .banco-badge {{
        display: inline-block; background: {emp_cfg.get('color_primario', '#1e40af')}; color: white;
        padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600;
        margin-bottom: 0.5rem;
    }}
    .footer {{ text-align: center; color: {emp_cfg.get('color_secundario', '#94a3b8')}; font-size: 0.85rem; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid {card_border}; }}
    /* Modo oscuro inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
    }}
    .stSidebar {{ background-color: {sidebar_bg} !important; }}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: LOGIN
# ═══════════════════════════════════════════════════════════════════════
if st.session_state["page"] == "login":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Logo
        logo_url = emp_cfg.get('logo_url', '')
        if logo_url:
            st.image(logo_url, width=120)
        else:
            st.markdown("<h1 style='text-align:center; font-size:3rem; margin-bottom:0;'>📊</h1>", unsafe_allow_html=True)

        nombre_emp = emp_cfg.get('nombre_empresa', 'ConciliApp PRO')
        st.markdown(f'<div class="main-header" style="text-align:center;">{nombre_emp}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header" style="text-align:center;">Conciliacion bancaria inteligente</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="login-box">', unsafe_allow_html=True)
            tab_login, tab_reg = st.tabs(["🔑 Iniciar sesion", "📝 Registrarse"])

            with tab_login:
                username = st.text_input("Usuario", key="login_user")
                password = st.text_input("Contraseña", type="password", key="login_pass")
                if st.button("Ingresar", type="primary", use_container_width=True):
                    ok, uid, nombre = validar_login(username, password)
                    if ok:
                        st.session_state["user_id"] = uid
                        st.session_state["user_name"] = nombre or username
                        # Cargar modo oscuro del usuario
                        cfg = obtener_config_empresa(uid)
                        st.session_state["dark_mode"] = bool(cfg.get("modo_oscuro", 0))
                        st.session_state["page"] = "dashboard"
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos")

            with tab_reg:
                new_user = st.text_input("Nuevo usuario", key="reg_user")
                new_pass = st.text_input("Contraseña", type="password", key="reg_pass")
                new_nombre = st.text_input("Nombre completo", key="reg_nombre")
                new_email = st.text_input("Email", key="reg_email")
                if st.button("Crear cuenta", use_container_width=True):
                    if not new_user or not new_pass:
                        st.error("Usuario y contraseña son obligatorios")
                    else:
                        ok, msg = crear_usuario(new_user, new_pass, new_nombre, new_email)
                        if ok:
                            st.success(msg)
                            st.info("Ahora inicia sesion con tus credenciales")
                        else:
                            st.error(msg)

            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="footer">{nombre_emp} © 2026</div>', unsafe_allow_html=True)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════
# PAGINAS LOGUEADAS
# ═══════════════════════════════════════════════════════════════════════
user_id = st.session_state["user_id"]
user_name = st.session_state["user_name"]

# Recargar config empresa
emp_cfg = obtener_config_empresa(user_id)
num_pendientes = contar_pendientes(user_id)

with st.sidebar:
    # Logo en sidebar
    logo_url = emp_cfg.get('logo_url', '')
    if logo_url:
        st.image(logo_url, width=80)
    st.markdown(f"### 👤 {user_name}")
    if num_pendientes > 0:
        st.markdown(f"🔴 **{num_pendientes} pendientes** arrastrados")
    st.markdown("---")

    # Toggle modo oscuro
    dark_toggle = st.toggle("🌙 Modo oscuro", value=st.session_state.get("dark_mode", False))
    if dark_toggle != st.session_state.get("dark_mode", False):
        st.session_state["dark_mode"] = dark_toggle
        # Guardar en DB
        cfg = emp_cfg.copy()
        cfg["modo_oscuro"] = 1 if dark_toggle else 0
        guardar_config_empresa(user_id, cfg)
        st.rerun()

    st.markdown("---")

    if st.button("🏠 Dashboard", use_container_width=True):
        go_to("dashboard")
    if st.button("📥 Nueva conciliacion", use_container_width=True):
        go_to("nueva")
    if st.button("📦 Pendientes", use_container_width=True):
        go_to("pendientes")
    if st.button("💾 Mis perfiles", use_container_width=True):
        go_to("perfiles")
    if st.button("📜 Historial", use_container_width=True):
        go_to("historial")
    if st.button("⚙️ Mi empresa", use_container_width=True):
        go_to("empresa")
    st.markdown("---")
    if st.button("🚪 Cerrar sesion", use_container_width=True):
        logout()

# ── Header comun ─────────────────────────────────────────────────────────
col_logo, col_title = st.columns([0.12, 0.88])
with col_logo:
    if logo_url:
        st.image(logo_url, width=60)
    else:
        st.markdown("<h1 style='font-size:3rem; margin:0;'>📊</h1>", unsafe_allow_html=True)
with col_title:
    nombre_emp = emp_cfg.get('nombre_empresa', 'ConciliApp PRO')
    st.markdown(f'<div class="main-header">{nombre_emp}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Conciliacion bancaria inteligente</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════
if st.session_state["page"] == "dashboard":
    st.markdown("### 📈 Dashboard")

    perfiles = listar_perfiles(user_id)
    historial = obtener_historial(user_id, limite=10)
    pendientes_list = obtener_pendientes(user_id)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-box blue"><div class="metric-value">{len(perfiles)}</div><div class="metric-label">Perfiles guardados</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-box green"><div class="metric-value">{len(historial)}</div><div class="metric-label">Conciliaciones</div></div>', unsafe_allow_html=True)
    with c3:
        tasa_promedio = 0
        if historial:
            tasa_promedio = round(sum([h["conciliados"]/max(h["total_registros"],1)*100 for h in historial]) / len(historial), 1)
        st.markdown(f'<div class="metric-box orange"><div class="metric-value">{tasa_promedio}%</div><div class="metric-label">Tasa de exito</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-box" style="background: linear-gradient(135deg, #f5576c 0%, #ff6b6b 100%);"><div class="metric-value">{len(pendientes_list)}</div><div class="metric-label">Pendientes arrastrados</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Alerta si hay muchos pendientes
    if len(pendientes_list) > 10:
        st.markdown(f'<div class="alerta-box">⚠️ Tenes {len(pendientes_list)} pendientes sin resolver. Revisalos en la seccion "Pendientes".</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 💾 Perfiles recientes")
        if not perfiles:
            st.info("No tenes perfiles guardados.")
        else:
            for p in perfiles[:5]:
                with st.container():
                    st.markdown(f"<div class='perfil-card'><b>{p['nombre']}</b><br><small>Actualizado: {p['actualizado_en'][:10]}</small></div>", unsafe_allow_html=True)

    with col_b:
        st.markdown("#### 📜 Ultimas conciliaciones")
        if not historial:
            st.info("Todavia no realizaste ninguna conciliacion.")
        else:
            for h in historial[:5]:
                st.caption(f"🗓️ {h['ejecutada_en'][:16]} | {h['modo']} | {h['conciliados']}/{h['total_registros']} conciliados")

    # Grafico de evolucion
    if historial:
        st.markdown("---")
        st.markdown("#### 📊 Evolucion de conciliaciones")
        df_hist = pd.DataFrame(historial)
        df_hist['ejecutada_en'] = pd.to_datetime(df_hist['ejecutada_en'], errors='coerce')
        df_hist = df_hist.dropna(subset=['ejecutada_en'])
        if not df_hist.empty:
            df_hist['mes'] = df_hist['ejecutada_en'].dt.strftime('%Y-%m')
            evol = df_hist.groupby('mes').agg({
                'conciliados': 'sum',
                'pendientes': 'sum'
            }).reset_index()
            fig = px.bar(evol, x='mes', y=['conciliados', 'pendientes'],
                        labels={'value': 'Cantidad', 'mes': 'Mes'},
                        color_discrete_map={'conciliados': emp_cfg.get('color_exito', '#11998e'),
                                           'pendientes': emp_cfg.get('color_alerta', '#f5576c')})
            fig.update_layout(height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: NUEVA CONCILIACION
# ═══════════════════════════════════════════════════════════════════════
elif st.session_state["page"] == "nueva":
    st.markdown("### 📥 Nueva conciliacion")

    # Cargar perfiles para selector
    perfiles = listar_perfiles(user_id)
    perfil_opciones = ["Sin perfil (configurar manualmente)"] + [p["nombre"] for p in perfiles]
    perfil_sel = st.selectbox("Cargar perfil existente", perfil_opciones)

    config_cargada = None
    if perfil_sel != "Sin perfil (configurar manualmente)":
        for p in perfiles:
            if p["nombre"] == perfil_sel:
                config_cargada = p["config"]
                st.success(f"✅ Perfil '{perfil_sel}' cargado.")
                break

    # Configuracion rapida
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        modo = st.selectbox("Modo", ["1 a 1 (detalle)", "Agregado (por dia / lote)"])
    with col2:
        tolerancia_pct = st.slider("Tolerancia importe (%)", 0.0, 10.0, 0.5, 0.1) / 100.0
    with col3:
        tolerancia_dias = st.slider("Tolerancia dias", 0, 7, 1)
    with col4:
        alerta_diff = st.slider("Alerta si dif. > $", 0.0, 5000.0, float(emp_cfg.get('alerta_diferencia', 100.0)), 50.0)
    exigir_cuit = st.toggle("Exigir CUIT")

    # Mostrar pendientes arrastrados
    pendientes_previos = obtener_pendientes(user_id)
    if pendientes_previos:
        st.markdown("---")
        with st.expander(f"📦 Incluir {len(pendientes_previos)} pendientes del periodo anterior", expanded=False):
            incluir_pendientes = st.checkbox("Agregar pendientes al archivo del sistema", value=False)
            if incluir_pendientes:
                st.info("Los pendientes se agregaran automaticamente al sistema al ejecutar.")
    else:
        incluir_pendientes = False

    # Carga de archivos
    st.markdown("---")
    st.markdown("### 📁 Archivos")
    col_b, col_s = st.columns(2)
    with col_b:
        st.markdown("**🏦 Extracto bancario**")
        archivo_banco = st.file_uploader("Banco", type=["xlsx","xls","csv"], key="banco", label_visibility="collapsed")
    with col_s:
        st.markdown("**💻 Registro del sistema**")
        archivo_sistema = st.file_uploader("Sistema", type=["xlsx","xls","csv"], key="sistema", label_visibility="collapsed")

    if archivo_banco and archivo_sistema:
        bytes_banco = archivo_banco.getvalue()
        bytes_sistema = archivo_sistema.getvalue()

        # Leer archivos
        fila_b, _ = detectar_fila_encabezado(bytes_banco)
        fila_s, _ = detectar_fila_encabezado(bytes_sistema)

        if config_cargada:
            fila_b = config_cargada.get("banco_fila_encabezado", fila_b)
            fila_s = config_cargada.get("sistema_fila_encabezado", fila_s)

        df_banco = leer_archivo(bytes_banco, fila_encabezado=fila_b)
        df_sistema = leer_archivo(bytes_sistema, fila_encabezado=fila_s)

        # Detectar banco automaticamente
        banco_detectado = detectar_banco(df_banco)
        if banco_detectado != 'Banco no detectado':
            st.markdown(f'<span class="banco-badge">🏦 {banco_detectado} detectado</span>', unsafe_allow_html=True)

        st.success(f"✅ Banco: {len(df_banco)} filas | Sistema: {len(df_sistema)} filas")

        # Si hay pendientes para incluir, agregarlos al sistema
        if incluir_pendientes and pendientes_previos:
            filas_pendientes = []
            for p in pendientes_previos:
                filas_pendientes.append({
                    'Fecha': p['fecha'],
                    'Concepto': f"[PENDIENTE] {p['concepto_banco']}",
                    'Importe': p['importe_banco']
                })
            df_pend = pd.DataFrame(filas_pendientes)
            # Intentar mapear columnas
            cols_auto = detectar_columnas_recomendadas(df_sistema)
            if cols_auto.get('fecha') and cols_auto.get('importe'):
                df_pend.columns = [cols_auto.get('fecha', 'Fecha'), cols_auto.get('concepto', 'Concepto'), cols_auto.get('importe', 'Importe')]
            df_sistema = pd.concat([df_sistema, df_pend], ignore_index=True)
            st.info(f"📦 Se agregaron {len(filas_pendientes)} pendientes al sistema")

        # Detectar columnas
        cols_b_auto = detectar_columnas_recomendadas(df_banco)
        cols_s_auto = detectar_columnas_recomendadas(df_sistema)

        def get_cfg(tipo, campo, auto_val):
            if config_cargada and f"{tipo}_{campo}" in config_cargada:
                return config_cargada[f"{tipo}_{campo}"]
            return auto_val

        def idx_safe(val, lst):
            return lst.index(val) if val in lst else 0

        # ── CONFIGURAR BANCO ────────────────────────────────────────────
        with st.expander("🏦 Configurar Banco", expanded=True):
            cols_b = list(df_banco.columns)
            cb1, cb2 = st.columns(2)
            with cb1:
                col_fecha_b = st.selectbox("Fecha", cols_b, index=idx_safe(get_cfg("banco","fecha",cols_b_auto.get("fecha")), cols_b), key="cb_fecha")
                col_importe_b = st.selectbox("Importe", cols_b, index=idx_safe(get_cfg("banco","importe",cols_b_auto.get("importe")), cols_b), key="cb_importe")
            with cb2:
                col_concepto_b = st.selectbox("Concepto", cols_b, index=idx_safe(get_cfg("banco","concepto",cols_b_auto.get("concepto")), cols_b), key="cb_concepto")
                if exigir_cuit:
                    col_cuit_b = st.selectbox("CUIT", [None]+cols_b, index=idx_safe(get_cfg("banco","cuit",None), [None]+cols_b), key="cb_cuit")
                else:
                    col_cuit_b = None

            diag_b_f = diagnosticar_columna(df_banco, col_fecha_b, 'fecha')
            diag_b_i = diagnosticar_columna(df_banco, col_importe_b, 'importe')
            db1, db2 = st.columns(2)
            with db1:
                if 'error' not in diag_b_f:
                    color = "diag-ok" if diag_b_f['tasa'] >= 80 else "diag-warn" if diag_b_f['tasa'] >= 50 else "diag-error"
                    st.markdown(f'<span class="{color}">📅 Fechas: {diag_b_f["validas"]}/{diag_b_f["total"]} validas</span>', unsafe_allow_html=True)
            with db2:
                if 'error' not in diag_b_i:
                    color = "diag-ok" if diag_b_i['tasa'] >= 80 else "diag-warn" if diag_b_i['tasa'] >= 50 else "diag-error"
                    st.markdown(f'<span class="{color}">💰 Importes: {diag_b_i["no_cero"]}/{diag_b_i["total"]} validos</span>', unsafe_allow_html=True)

        # ── CONFIGURAR SISTEMA ──────────────────────────────────────────
        with st.expander("💻 Configurar Sistema", expanded=True):
            cols_s = list(df_sistema.columns)
            cs1, cs2 = st.columns(2)
            with cs1:
                col_fecha_s = st.selectbox("Fecha", cols_s, index=idx_safe(get_cfg("sistema","fecha",cols_s_auto.get("fecha")), cols_s), key="cs_fecha")
                col_importe_s = st.selectbox("Importe", cols_s, index=idx_safe(get_cfg("sistema","importe",cols_s_auto.get("importe")), cols_s), key="cs_importe")
            with cs2:
                col_concepto_s = st.selectbox("Concepto", cols_s, index=idx_safe(get_cfg("sistema","concepto",cols_s_auto.get("concepto")), cols_s), key="cs_concepto")
                if exigir_cuit:
                    col_cuit_s = st.selectbox("CUIT", [None]+cols_s, index=idx_safe(get_cfg("sistema","cuit",None), [None]+cols_s), key="cs_cuit")
                else:
                    col_cuit_s = None

            diag_s_f = diagnosticar_columna(df_sistema, col_fecha_s, 'fecha')
            diag_s_i = diagnosticar_columna(df_sistema, col_importe_s, 'importe')
            ds1, ds2 = st.columns(2)
            with ds1:
                if 'error' not in diag_s_f:
                    color = "diag-ok" if diag_s_f['tasa'] >= 80 else "diag-warn" if diag_s_f['tasa'] >= 50 else "diag-error"
                    st.markdown(f'<span class="{color}">📅 Fechas: {diag_s_f["validas"]}/{diag_s_f["total"]} validas</span>', unsafe_allow_html=True)
            with ds2:
                if 'error' not in diag_s_i:
                    color = "diag-ok" if diag_s_i['tasa'] >= 80 else "diag-warn" if diag_s_i['tasa'] >= 50 else "diag-error"
                    st.markdown(f'<span class="{color}">💰 Importes: {diag_s_i["no_cero"]}/{diag_s_i["total"]} validos</span>', unsafe_allow_html=True)

        # ── GUARDAR PERFIL + EJECUTAR ────────────────────────────────────
        st.markdown("---")
        col_save, col_run = st.columns([1, 2])
        with col_save:
            nombre_nuevo_perfil = st.text_input("Nombre del perfil", value=perfil_sel if perfil_sel != "Sin perfil (configurar manualmente)" else "", placeholder="Ej: MiNegocio_BancoGalicia")
            if st.button("💾 Guardar perfil", use_container_width=True) and nombre_nuevo_perfil:
                config_guardar = {
                    "banco_fila_encabezado": fila_b,
                    "sistema_fila_encabezado": fila_s,
                    "banco_fecha": col_fecha_b,
                    "banco_importe": col_importe_b,
                    "banco_concepto": col_concepto_b,
                    "banco_cuit": col_cuit_b,
                    "sistema_fecha": col_fecha_s,
                    "sistema_importe": col_importe_s,
                    "sistema_concepto": col_concepto_s,
                    "sistema_cuit": col_cuit_s,
                }
                guardar_perfil(user_id, nombre_nuevo_perfil, config_guardar)
                st.success(f"✅ Perfil '{nombre_nuevo_perfil}' guardado")

        with col_run:
            if st.button("🚀 Ejecutar conciliacion", type="primary", use_container_width=True):
                with st.spinner("Conciliando..."):
                    try:
                        if modo == "1 a 1 (detalle)":
                            resultado = conciliar(
                                df_banco, df_sistema,
                                col_fecha_banco=col_fecha_b,
                                col_importe_banco=col_importe_b,
                                col_desc_banco=col_concepto_b,
                                col_fecha_sistema=col_fecha_s,
                                col_importe_sistema=col_importe_s,
                                col_desc_sistema=col_concepto_s,
                                col_cuit_banco=col_cuit_b,
                                col_cuit_sistema=col_cuit_s,
                                tolerancia_pct=tolerancia_pct,
                                tolerancia_dias=tolerancia_dias,
                                exigir_cuit=exigir_cuit,
                            )
                        else:
                            resultado = conciliar_agregado(
                                df_banco, df_sistema,
                                col_fecha_banco=col_fecha_b,
                                col_importe_banco=col_importe_b,
                                col_desc_banco=col_concepto_b,
                                col_fecha_sistema=col_fecha_s,
                                col_importe_sistema=col_importe_s,
                                tolerancia_pct=tolerancia_pct,
                                tolerancia_dias=tolerancia_dias,
                            )

                        # Guardar en session state
                        st.session_state["resultado"] = resultado
                        st.session_state["modo"] = modo

                        # Guardar en historial
                        total = len(resultado)
                        conciliados = len(resultado[resultado['Estado'].str.contains('CONCILIADO')])
                        pendientes_count = len(resultado[resultado['Estado'] == 'PENDIENTE'])
                        sin_mov = len(resultado[resultado['Estado'] == 'SIN_MOVIMIENTO_BANCO'])
                        total_banco = resultado['Importe_Banco'].sum()
                        total_sistema = resultado['Importe_Sistema'].sum()
                        diff = total_banco - total_sistema

                        # Guardar pendientes para arrastrar
                        df_pendientes = resultado[resultado['Estado'] == 'PENDIENTE'].copy()
                        if not df_pendientes.empty:
                            periodo_actual = datetime.now().strftime('%Y-%m')
                            guardar_pendientes(user_id, df_pendientes, periodo_actual)
                            st.info(f"📦 {len(df_pendientes)} pendientes guardados para el proximo periodo")

                        perfil_id = None
                        for p in perfiles:
                            if p["nombre"] == perfil_sel:
                                perfil_id = p["id"]
                                break

                        guardar_conciliacion(user_id, perfil_id, {
                            "archivo_banco": archivo_banco.name,
                            "archivo_sistema": archivo_sistema.name,
                            "modo": modo,
                            "total": total,
                            "conciliados": conciliados,
                            "pendientes": pendientes_count,
                            "sin_movimiento": sin_mov,
                            "total_banco": total_banco,
                            "total_sistema": total_sistema,
                        })

                        st.success("✅ Conciliacion completada y guardada")

                        # ALERTA DE DIFERENCIA
                        if abs(diff) > alerta_diff:
                            st.markdown(f'<div class="alerta-box">🚨 ALERTA: La diferencia de ${abs(diff):,.2f} supera el limite configurado de ${alerta_diff:,.2f}</div>', unsafe_allow_html=True)

                        # Mostrar resultados inline
                        st.markdown("---")
                        st.markdown("### 📈 Resultados")

                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.markdown(f'<div class="metric-box green"><div class="metric-value">{conciliados}</div><div class="metric-label">Conciliados</div></div>', unsafe_allow_html=True)
                        with m2:
                            st.markdown(f'<div class="metric-box orange"><div class="metric-value">{pendientes_count}</div><div class="metric-label">Pendientes</div></div>', unsafe_allow_html=True)
                        with m3:
                            st.markdown(f'<div class="metric-box blue"><div class="metric-value">{sin_mov}</div><div class="metric-label">Sin mov. banco</div></div>', unsafe_allow_html=True)
                        with m4:
                            porc = round((conciliados/total*100), 1) if total > 0 else 0
                            st.markdown(f'<div class="metric-box"><div class="metric-value">{porc}%</div><div class="metric-label">Tasa de exito</div></div>', unsafe_allow_html=True)

                        t1, t2, t3 = st.columns(3)
                        with t1:
                            st.metric("Total Banco", f"${total_banco:,.2f}")
                        with t2:
                            st.metric("Total Sistema", f"${total_sistema:,.2f}")
                        with t3:
                            st.metric("Diferencia", f"${diff:,.2f}", delta=f"{diff:,.2f}", delta_color="inverse")

                        # Graficos
                        g1, g2 = st.columns(2)
                        colors = {'CONCILIADO': emp_cfg.get('color_exito', '#11998e'), 'CONCILIADO (agregado)': '#38ef7d', 'PENDIENTE': emp_cfg.get('color_alerta', '#f5576c'), 'SIN_MOVIMIENTO_BANCO': '#4facfe'}
                        with g1:
                            ec = resultado['Estado'].value_counts().reset_index()
                            ec.columns = ['Estado', 'Cantidad']
                            fig = px.pie(ec, values='Cantidad', names='Estado', color='Estado', color_discrete_map=colors, hole=0.55)
                            fig.update_layout(showlegend=False, height=300, paper_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig, use_container_width=True)
                        with g2:
                            if 'Fecha' in resultado.columns:
                                df_f = resultado.dropna(subset=['Fecha']).copy()
                                if not df_f.empty:
                                    df_f['Fecha'] = pd.to_datetime(df_f['Fecha'], errors='coerce')
                                    df_f = df_f.dropna(subset=['Fecha'])
                                    if not df_f.empty:
                                        df_f['Fecha_str'] = df_f['Fecha'].dt.strftime('%Y-%m-%d')
                                        agrup = df_f.groupby(['Fecha_str', 'Estado']).size().reset_index(name='Cantidad')
                                        fig = px.bar(agrup, x='Fecha_str', y='Cantidad', color='Estado', color_discrete_map=colors, barmode='group')
                                        fig.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                                        st.plotly_chart(fig, use_container_width=True)

                        # Tablas
                        tab_conc, tab_pend, tab_sin = st.tabs(["✅ Conciliados", "⚠️ Pendientes", "❓ Sin mov."])
                        with tab_conc:
                            st.dataframe(resultado[resultado['Estado'].str.contains('CONCILIADO')], use_container_width=True, hide_index=True)
                        with tab_pend:
                            st.dataframe(resultado[resultado['Estado'] == 'PENDIENTE'], use_container_width=True, hide_index=True)
                        with tab_sin:
                            st.dataframe(resultado[resultado['Estado'] == 'SIN_MOVIMIENTO_BANCO'], use_container_width=True, hide_index=True)

                        # Exportar
                        def to_excel(df):
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                df.to_excel(writer, index=False, sheet_name='Resultado')
                            return output.getvalue()

                        col_ex1, col_ex2 = st.columns(2)
                        with col_ex1:
                            st.download_button("📥 Excel completo", data=to_excel(resultado),
                                file_name=f"conciliapp_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                        with col_ex2:
                            csv = resultado.to_csv(index=False).encode('utf-8')
                            st.download_button("📥 CSV", data=csv,
                                file_name=f"conciliapp_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv", use_container_width=True)

                    except Exception as e:
                        st.error(f"❌ Error: {e}")

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: PENDIENTES (PASO 5)
# ═══════════════════════════════════════════════════════════════════════
elif st.session_state["page"] == "pendientes":
    st.markdown("### 📦 Pendientes del periodo anterior")
    st.markdown("Aca podes ver los movimientos que quedaron sin conciliar en ejecuciones anteriores.")

    pendientes_list = obtener_pendientes(user_id)
    if not pendientes_list:
        st.info("🎉 No tenes pendientes arrastrados. Todas las conciliaciones cerraron correctamente.")
    else:
        st.markdown(f"**Total de pendientes:** {len(pendientes_list)}")

        # Convertir a DataFrame para mostrar
        df_pend = pd.DataFrame(pendientes_list)
        if 'creado_en' in df_pend.columns:
            df_pend['creado_en'] = pd.to_datetime(df_pend['creado_en'], errors='coerce').dt.strftime('%Y-%m-%d')

        st.dataframe(df_pend[['concepto_banco', 'importe_banco', 'fecha', 'periodo', 'creado_en']], 
                    use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### ✅ Resolver pendientes")
        st.markdown("Selecciona los pendientes que ya conciliaste en otra ejecucion:")

        for p in pendientes_list[:20]:  # Mostrar max 20 para no saturar
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"<div class='perfil-card'><b>{p['concepto_banco']}</b><br><small>${p['importe_banco']:,.2f} | {p['fecha']} | Periodo: {p['periodo']}</small></div>", unsafe_allow_html=True)
            with col2:
                if st.button("✅ Resolver", key=f"res_{p['id']}"):
                    resolver_pendiente(p['id'], user_id)
                    st.success("Pendiente marcado como resuelto")
                    st.rerun()

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: PERFILES
# ═══════════════════════════════════════════════════════════════════════
elif st.session_state["page"] == "perfiles":
    st.markdown("### 💾 Mis perfiles de configuracion")

    perfiles = listar_perfiles(user_id)
    if not perfiles:
        st.info("No tenes perfiles guardados. Crea uno desde 'Nueva conciliacion'.")
    else:
        for p in perfiles:
            with st.container():
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    cfg = p["config"]
                    st.markdown(f"<div class='perfil-card'><b>📁 {p['nombre']}</b><br><small>Creado: {p['creado_en'][:10]} | Actualizado: {p['actualizado_en'][:10]}</small><br><small>Banco: {cfg.get('banco_fecha','?')} / {cfg.get('banco_importe','?')} | Sistema: {cfg.get('sistema_fecha','?')} / {cfg.get('sistema_importe','?')}</small></div>", unsafe_allow_html=True)
                with col2:
                    if st.button("📂 Usar", key=f"use_{p['id']}"):
                        st.session_state["perfil_a_usar"] = p["nombre"]
                        go_to("nueva")
                with col3:
                    if st.button("🗑️ Borrar", key=f"del_{p['id']}"):
                        eliminar_perfil(user_id, p["id"])
                        st.success(f"Perfil '{p['nombre']}' eliminado")
                        st.rerun()

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: HISTORIAL
# ═══════════════════════════════════════════════════════════════════════
elif st.session_state["page"] == "historial":
    st.markdown("### 📜 Historial de conciliaciones")

    historial = obtener_historial(user_id, limite=100)
    if not historial:
        st.info("Todavia no realizaste ninguna conciliacion.")
    else:
        for h in historial:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.markdown(f"**🗓️ {h['ejecutada_en'][:16]}** | {h['modo']}")
                    st.caption(f"Banco: {h['nombre_archivo_banco']} | Sistema: {h['nombre_archivo_sistema']}")
                with col2:
                    tasa = round(h['conciliados']/max(h['total_registros'],1)*100, 1)
                    st.markdown(f"✅ {h['conciliados']} conciliados | ⚠️ {h['pendientes']} pendientes")
                    st.caption(f"Tasa de exito: {tasa}%")
                with col3:
                    diff = h['total_banco'] - h['total_sistema']
                    color_diff = emp_cfg.get('color_alerta', '#f5576c') if abs(diff) > emp_cfg.get('alerta_diferencia', 100) else emp_cfg.get('color_exito', '#11998e')
                    st.markdown(f"<span style='color:{color_diff}; font-weight:700;'>Diferencia: ${diff:,.2f}</span>")
                st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: CONFIG EMPRESA
# ═══════════════════════════════════════════════════════════════════════
elif st.session_state["page"] == "empresa":
    st.markdown("### ⚙️ Configuracion de mi empresa")
    st.markdown("Personaliza los colores, el nombre y el logo de tu app.")

    cfg = obtener_config_empresa(user_id)

    with st.form("config_empresa"):
        nombre_empresa = st.text_input("Nombre de la empresa", value=cfg.get('nombre_empresa', 'ConciliApp PRO'))
        logo_url = st.text_input("URL del logo (dejalo vacio para usar el icono por defecto)", value=cfg.get('logo_url', ''), placeholder="https://tusitio.com/logo.png")

        st.markdown("#### 🎨 Colores")
        col1, col2 = st.columns(2)
        with col1:
            color_primario = st.color_picker("Color principal", value=cfg.get('color_primario', '#1e40af'))
            color_exito = st.color_picker("Color de exito", value=cfg.get('color_exito', '#11998e'))
        with col2:
            color_alerta = st.color_picker("Color de alerta", value=cfg.get('color_alerta', '#f5576c'))
            color_secundario = st.color_picker("Color secundario", value=cfg.get('color_secundario', '#64748b'))

        st.markdown("#### 🔔 Alertas")
        alerta_diferencia = st.number_input("Alertar si la diferencia supera ($)", min_value=0.0, value=float(cfg.get('alerta_diferencia', 100.0)), step=50.0)

        submitted = st.form_submit_button("💾 Guardar configuracion", use_container_width=True)
        if submitted:
            nueva_config = {
                'nombre_empresa': nombre_empresa,
                'logo_url': logo_url,
                'color_primario': color_primario,
                'color_secundario': color_secundario,
                'color_exito': color_exito,
                'color_alerta': color_alerta,
                'modo_oscuro': 1 if st.session_state.get("dark_mode", False) else 0,
                'alerta_diferencia': alerta_diferencia,
            }
            guardar_config_empresa(user_id, nueva_config)
            st.success("✅ Configuracion guardada. Recarga la pagina para ver los cambios.")
            st.balloons()

    st.markdown("---")
    st.markdown("#### 🖼️ Como subir tu logo")
    st.info("""
    1. Subi tu logo a un servicio como [Imgur](https://imgur.com) o [Cloudinary](https://cloudinary.com)
    2. Copia el link directo a la imagen (termina en .png o .jpg)
    3. Pegalo en el campo "URL del logo" de arriba
    """)

st.markdown(f'<div class="footer">{emp_cfg.get("nombre_empresa", "ConciliApp PRO")} © 2026 — Multi-usuario con perfiles persistentes</div>', unsafe_allow_html=True)
