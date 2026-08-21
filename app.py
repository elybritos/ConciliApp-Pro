# -*- coding: utf-8 -*-
"""
ConciliApp PRO — Conciliacion Bancaria con Login y Perfiles
Version multi-usuario con base de datos SQLite.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
import os

from motor_conciliacion import (
    leer_archivo, detectar_fila_encabezado, detectar_columnas_recomendadas,
    diagnosticar_columna, conciliar, conciliar_agregado
)
from database import (
    crear_usuario, validar_login, guardar_perfil, listar_perfiles,
    eliminar_perfil, guardar_conciliacion, obtener_historial
)

# ── Estado de sesion ─────────────────────────────────────────────────────
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "login"

def logout():
    for key in ["user_id", "user_name", "page", "resultado", "modo"]:
        st.session_state[key] = None if key != "page" else "login"
    st.rerun()

def go_to(page):
    st.session_state["page"] = page
    st.rerun()

# ── Estilos ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ConciliApp PRO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed" if st.session_state["user_id"] is None else "expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header { font-size: 2.8rem; font-weight: 700; color: #1e3a5f; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.1rem; color: #64748b; margin-bottom: 2rem; }
    .login-box { max-width: 400px; margin: 0 auto; padding: 2rem; background: #f8fafc; border-radius: 16px; border: 1px solid #e2e8f0; }
    .metric-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px; padding: 1.2rem; color: white;
        text-align: center; box-shadow: 0 4px 15px rgba(102,126,234,0.3);
    }
    .metric-box.green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .metric-box.orange { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
    .metric-box.blue { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
    .metric-value { font-size: 2.2rem; font-weight: 700; margin: 0; }
    .metric-label { font-size: 0.9rem; opacity: 0.9; margin-top: 0.3rem; }
    .perfil-card {
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 1.2rem; margin-bottom: 0.8rem; transition: all 0.2s;
    }
    .perfil-card:hover { border-color: #1e40af; box-shadow: 0 2px 8px rgba(30,64,175,0.1); }
    .diag-ok { color: #059669; font-weight: 600; }
    .diag-warn { color: #d97706; font-weight: 600; }
    .diag-error { color: #dc2626; font-weight: 600; }
    .footer { text-align: center; color: #94a3b8; font-size: 0.85rem; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: LOGIN
# ═══════════════════════════════════════════════════════════════════════
if st.session_state["page"] == "login":
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center; font-size:3rem; margin-bottom:0;'>📊</h1>", unsafe_allow_html=True)
        st.markdown('<div class="main-header" style="text-align:center;">ConciliApp PRO</div>', unsafe_allow_html=True)
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

    st.markdown('<div class="footer">ConciliApp PRO © 2026</div>', unsafe_allow_html=True)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════
# PAGINAS LOGUEADAS
# ═══════════════════════════════════════════════════════════════════════
user_id = st.session_state["user_id"]
user_name = st.session_state["user_name"]

with st.sidebar:
    st.markdown(f"### 👤 {user_name}")
    st.markdown("---")

    if st.button("🏠 Dashboard", use_container_width=True):
        go_to("dashboard")
    if st.button("📥 Nueva conciliacion", use_container_width=True):
        go_to("nueva")
    if st.button("💾 Mis perfiles", use_container_width=True):
        go_to("perfiles")
    if st.button("📜 Historial", use_container_width=True):
        go_to("historial")
    st.markdown("---")
    if st.button("🚪 Cerrar sesion", use_container_width=True):
        logout()

# ── Header comun ─────────────────────────────────────────────────────────
col_logo, col_title = st.columns([0.12, 0.88])
with col_logo:
    st.markdown("<h1 style='font-size:3rem; margin:0;'>📊</h1>", unsafe_allow_html=True)
with col_title:
    st.markdown('<div class="main-header">ConciliApp PRO</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Conciliacion bancaria inteligente</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# PAGINA: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════
if st.session_state["page"] == "dashboard":
    st.markdown("### 📈 Dashboard")

    perfiles = listar_perfiles(user_id)
    historial = obtener_historial(user_id, limite=10)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-box blue"><div class="metric-value">{len(perfiles)}</div><div class="metric-label">Perfiles guardados</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-box green"><div class="metric-value">{len(historial)}</div><div class="metric-label">Conciliaciones realizadas</div></div>', unsafe_allow_html=True)
    with c3:
        tasa_promedio = 0
        if historial:
            tasa_promedio = round(sum([h["conciliados"]/max(h["total_registros"],1)*100 for h in historial]) / len(historial), 1)
        st.markdown(f'<div class="metric-box orange"><div class="metric-value">{tasa_promedio}%</div><div class="metric-label">Tasa promedio de exito</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 💾 Perfiles recientes")
        if not perfiles:
            st.info("No tenes perfiles guardados. Crea uno en 'Nueva conciliacion'.")
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
                st.success(f"✅ Perfil '{perfil_sel}' cargado. Las columnas se pre-seleccionaron.")
                break

    # Configuracion rapida
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        modo = st.selectbox("Modo", ["1 a 1 (detalle)", "Agregado (por dia / lote)"])
    with col2:
        tolerancia_pct = st.slider("Tolerancia importe (%)", 0.0, 10.0, 0.5, 0.1) / 100.0
    with col3:
        tolerancia_dias = st.slider("Tolerancia dias", 0, 7, 1)
    exigir_cuit = st.toggle("Exigir CUIT")

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

        # Si hay perfil cargado, usar su fila de encabezado
        if config_cargada:
            fila_b = config_cargada.get("banco_fila_encabezado", fila_b)
            fila_s = config_cargada.get("sistema_fila_encabezado", fila_s)

        df_banco = leer_archivo(bytes_banco, fila_encabezado=fila_b)
        df_sistema = leer_archivo(bytes_sistema, fila_encabezado=fila_s)

        st.success(f"✅ Banco: {len(df_banco)} filas | Sistema: {len(df_sistema)} filas")

        # Detectar columnas
        cols_b_auto = detectar_columnas_recomendadas(df_banco)
        cols_s_auto = detectar_columnas_recomendadas(df_sistema)

        # Funcion auxiliar para obtener valor de config o auto
        def get_cfg(tipo, campo, auto_val):
            if config_cargada and f"{tipo}_{campo}" in config_cargada:
                return config_cargada[f"{tipo}_{campo}"]
            return auto_val

        # ── CONFIGURAR BANCO ────────────────────────────────────────────
        with st.expander("🏦 Configurar Banco", expanded=True):
            cols_b = list(df_banco.columns)

            def idx_safe(val, lst):
                return lst.index(val) if val in lst else 0

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

            # Diagnostico
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
                        pendientes = len(resultado[resultado['Estado'] == 'PENDIENTE'])
                        sin_mov = len(resultado[resultado['Estado'] == 'SIN_MOVIMIENTO_BANCO'])
                        total_banco = resultado['Importe_Banco'].sum()
                        total_sistema = resultado['Importe_Sistema'].sum()

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
                            "pendientes": pendientes,
                            "sin_movimiento": sin_mov,
                            "total_banco": total_banco,
                            "total_sistema": total_sistema,
                        })

                        st.success("✅ Conciliacion completada y guardada en historial")

                        # Mostrar resultados inline
                        st.markdown("---")
                        st.markdown("### 📈 Resultados")

                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.markdown(f'<div class="metric-box green"><div class="metric-value">{conciliados}</div><div class="metric-label">Conciliados</div></div>', unsafe_allow_html=True)
                        with m2:
                            st.markdown(f'<div class="metric-box orange"><div class="metric-value">{pendientes}</div><div class="metric-label">Pendientes</div></div>', unsafe_allow_html=True)
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
                            diff = total_banco - total_sistema
                            st.metric("Diferencia", f"${diff:,.2f}", delta=f"{diff:,.2f}", delta_color="inverse")

                        # Graficos
                        g1, g2 = st.columns(2)
                        colors = {'CONCILIADO': '#11998e', 'CONCILIADO (agregado)': '#38ef7d', 'PENDIENTE': '#f5576c', 'SIN_MOVIMIENTO_BANCO': '#4facfe'}
                        with g1:
                            ec = resultado['Estado'].value_counts().reset_index()
                            ec.columns = ['Estado', 'Cantidad']
                            fig = px.pie(ec, values='Cantidad', names='Estado', color='Estado', color_discrete_map=colors, hole=0.55)
                            fig.update_layout(showlegend=False, height=300)
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
                                        fig.update_layout(height=300)
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
                    st.metric("Diferencia", f"${h['total_banco'] - h['total_sistema']:,.2f}")
                st.markdown("---")

st.markdown('<div class="footer">ConciliApp PRO © 2026 — Multi-usuario con perfiles persistentes</div>', unsafe_allow_html=True)
