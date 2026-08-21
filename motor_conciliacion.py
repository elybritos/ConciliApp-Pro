# -*- coding: utf-8 -*-
"""
motor_conciliacion.py
Motor de conciliacion bancaria generico.
Mejorado para archivos reales con encabezados en cualquier fila,
metadata, columnas desplazadas y formatos argentinos.
"""

import re
import io
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

PALABRAS_CLAVE_FECHA = ['fecha', 'date', 'fch', 'dia', 'periodo', 'vencimiento', 'vto']
PALABRAS_CLAVE_IMPORTE = ['importe', 'monto', 'debe', 'haber', 'valor', 'amount',
                         'total', 'neto', 'bruto', 'subtotal', 'credito', 'debito',
                         'crédito', 'débito', 'saldo']
PALABRAS_CLAVE_CONCEPTO = ['concepto', 'descripcion', 'detalle', 'desc', 'referencia',
                          'concept', 'cliente', 'proveedor', 'razon social', 'razón social',
                          'nombre', 'observacion', 'observación', 'comprobante',
                          'tipo', 'movimiento', 'transaccion', 'transacción',
                          'usuario', 'operacion', 'operación', 'sucursal']
PALABRAS_CLAVE_CUIT = ['cuit', 'cuil', 'dni', 'documento', 'identificacion', 'identificación']

TODAS_PALABRAS_CLAVE = (PALABRAS_CLAVE_FECHA + PALABRAS_CLAVE_IMPORTE +
                        PALABRAS_CLAVE_CONCEPTO + PALABRAS_CLAVE_CUIT)

METADATA_PATTERNS = [
    r'^pagina\s*\d+', r'^página\s*\d+', r'^page\s*\d+',
    r'^total\s*:', r'^empresa\s*:', r'^operador\s*:', r'^usuario\s*:',
    r'^fecha\s*:', r'^hora\s*:', r'^sucursal\s*:', r'^\d+\s*de\s*\d+$',
    r'^imprimir$', r'^exportar$', r'^reporte$', r'^listado$'
]

def _es_metadata(fila):
    texto = ' '.join([str(x).strip().lower() for x in fila if pd.notna(x)])
    for patron in METADATA_PATTERNS:
        if re.search(patron, texto):
            return True
    return False

def normalizar_texto(t):
    if pd.isna(t): return ''
    t = re.sub(r'[.,]', ' ', str(t))
    return re.sub(r'\s+', ' ', t).strip().upper()

def normalizar_importe(val):
    if pd.isna(val): return 0.0
    s = str(val).replace('$', '').replace(' ', '').replace('\xa0', '')
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        partes = s.split(',')
        if len(partes) == 2 and len(partes[1]) == 2 and len(partes[0]) > 0:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    try:
        return float(s)
    except:
        return 0.0

def normalizar_fecha(val):
    if pd.isna(val): return pd.NaT
    if isinstance(val, (datetime, pd.Timestamp)):
        return pd.Timestamp(val)
    if isinstance(val, (int, float)) and val > 30000 and val < 50000:
        try:
            return pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(val))
        except:
            pass
    s = str(val).strip()
    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
                '%Y/%m/%d', '%Y-%m-%d', '%m/%d/%Y', '%d%m%Y']:
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            continue
    try:
        return pd.to_datetime(val, dayfirst=True, errors='coerce')
    except:
        return pd.NaT

def _puntaje_fila_encabezado(fila):
    puntaje = 0
    celdas_no_vacias = 0
    for celda in fila:
        if pd.isna(celda):
            continue
        texto = str(celda).strip()
        if not texto:
            continue
        celdas_no_vacias += 1
        texto_norm = normalizar_texto(texto)
        for palabra in TODAS_PALABRAS_CLAVE:
            if palabra.upper() in texto_norm or texto_norm in palabra.upper():
                puntaje += 2
                break
        if not re.match(r'^[\d.,\/\-\s]+$', texto):
            puntaje += 0.5
    if celdas_no_vacias < 2:
        puntaje = 0
    return puntaje

def _es_excel(bytes_data):
    header = bytes_data[:8]
    if header[:2] == b'PK':
        return True
    if header[:4] == b'\xd0\xcf\x11\xe0':
        return True
    return False

def _leer_como_excel(bytes_data, header=None, nrows=None):
    try:
        return pd.read_excel(io.BytesIO(bytes_data), header=header, nrows=nrows, engine='openpyxl')
    except Exception:
        try:
            return pd.read_excel(io.BytesIO(bytes_data), header=header, nrows=nrows, engine='xlrd')
        except Exception:
            return pd.read_excel(io.BytesIO(bytes_data), header=header, nrows=nrows)

def _leer_como_csv(bytes_data, header=None, nrows=None):
    for encoding in ['utf-8', 'latin1', 'cp1252']:
        for sep in [None, ';', ',', '\t']:
            try:
                return pd.read_csv(
                    io.BytesIO(bytes_data),
                    sep=sep,
                    engine='python',
                    header=header,
                    nrows=nrows,
                    encoding=encoding,
                    on_bad_lines='skip'
                )
            except Exception:
                continue
    raise ValueError("No se pudo leer el archivo como CSV")

def detectar_fila_encabezado(bytes_data, max_filas=20):
    if _es_excel(bytes_data):
        df_raw = _leer_como_excel(bytes_data, header=None, nrows=max_filas)
    else:
        df_raw = _leer_como_csv(bytes_data, header=None, nrows=max_filas)
    mejor_fila = 0
    mejor_puntaje = -1
    for idx in range(min(max_filas, len(df_raw))):
        puntaje = _puntaje_fila_encabezado(df_raw.iloc[idx])
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_fila = idx
    return mejor_fila, df_raw

def leer_archivo(bytes_data, fila_encabezado=None):
    if fila_encabezado is None:
        fila_encabezado, _ = detectar_fila_encabezado(bytes_data)
    if _es_excel(bytes_data):
        df = _leer_como_excel(bytes_data, header=fila_encabezado)
    else:
        df = _leer_como_csv(bytes_data, header=fila_encabezado)
    df.columns = [str(c).strip() if c is not None else f'Col_{i}' for i, c in enumerate(df.columns)]
    mask = ~df.apply(lambda row: _es_metadata(row), axis=1)
    df = df[mask].reset_index(drop=True)
    df = df.dropna(how='all').reset_index(drop=True)
    return df

def _puntaje_coincidencia(col_norm, p_norm):
    if col_norm == p_norm:
        return 100
    if p_norm in col_norm or col_norm in p_norm:
        return 50
    col_compact = col_norm.replace(' ', '').replace('.', '')
    p_compact = p_norm.replace(' ', '').replace('.', '')
    if col_compact == p_compact:
        return 80
    if p_compact in col_compact or col_compact in p_compact:
        return 40
    col_words = set(col_norm.split())
    p_words = set(p_norm.split())
    interseccion = col_words & p_words
    if interseccion:
        return 20 * len(interseccion)
    return 0

def detectar_columna(df, patterns):
    mejor_col = None
    mejor_puntaje = -1
    for col in df.columns:
        if col is None:
            continue
        col_str = str(col).strip()
        col_norm = normalizar_texto(col_str)
        for p in patterns:
            p_norm = normalizar_texto(p)
            puntaje = _puntaje_coincidencia(col_norm, p_norm)
            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor_col = col_str
    return mejor_col if mejor_puntaje >= 20 else None

def detectar_columna_importe_por_contenido(df):
    mejor_col = None
    mejor_score = -1
    for col in df.columns:
        valores = df[col].dropna().head(50)
        if len(valores) < 3:
            continue
        numericos = 0
        suma = 0
        for v in valores:
            try:
                val = normalizar_importe(v)
                if val != 0:
                    numericos += 1
                    suma += abs(val)
            except:
                pass
        if numericos >= 3:
            score = numericos * (1 if 0 < suma < 1e9 else 0.1)
            if score > mejor_score:
                mejor_score = score
                mejor_col = col
    return mejor_col

def detectar_columnas_recomendadas(df):
    fecha = detectar_columna(df, PALABRAS_CLAVE_FECHA)
    importe = detectar_columna(df, PALABRAS_CLAVE_IMPORTE)
    concepto = detectar_columna(df, PALABRAS_CLAVE_CONCEPTO)
    cuit = detectar_columna(df, PALABRAS_CLAVE_CUIT)
    if importe is None:
        importe = detectar_columna_importe_por_contenido(df)
    return {
        'fecha': fecha,
        'importe': importe,
        'concepto': concepto,
        'cuit': cuit,
    }

def diagnosticar_datos(df, col_fecha, col_importe):
    resultados = {}
    if col_fecha and col_fecha in df.columns:
        fechas = df[col_fecha].apply(normalizar_fecha)
        validas = fechas.notna().sum()
        total = len(df)
        resultados['fecha'] = {
            'validas': int(validas),
            'total': int(total),
            'porcentaje': round(validas/total*100, 1) if total > 0 else 0,
            'ejemplos': df[col_fecha].dropna().head(3).tolist()
        }
    else:
        resultados['fecha'] = {'validas': 0, 'total': len(df), 'porcentaje': 0, 'ejemplos': []}
    if col_importe and col_importe in df.columns:
        importes = df[col_importe].apply(normalizar_importe)
        validos = (importes != 0).sum()
        total = len(df)
        resultados['importe'] = {
            'validos': int(validos),
            'total': int(total),
            'porcentaje': round(validos/total*100, 1) if total > 0 else 0,
            'suma': round(importes.sum(), 2),
            'ejemplos': df[col_importe].dropna().head(3).tolist()
        }
    else:
        resultados['importe'] = {'validos': 0, 'total': len(df), 'porcentaje': 0, 'suma': 0, 'ejemplos': []}
    return resultados

def conciliar(df_banco, df_sistema, col_fecha_banco, col_importe_banco, col_desc_banco,
              col_fecha_sistema, col_importe_sistema, col_desc_sistema,
              col_cuit_banco=None, col_cuit_sistema=None,
              tolerancia_pct=0.0, tolerancia_dias=0, exigir_cuit=False):
    df_banco = df_banco.copy()
    df_sistema = df_sistema.copy()
    df_banco['Fecha_norm'] = df_banco[col_fecha_banco].apply(normalizar_fecha)
    df_banco['Importe_norm'] = df_banco[col_importe_banco].apply(normalizar_importe)
    df_banco['Desc_norm'] = df_banco[col_desc_banco].astype(str).str.upper().str.strip()
    df_sistema['Fecha_norm'] = df_sistema[col_fecha_sistema].apply(normalizar_fecha)
    df_sistema['Importe_norm'] = df_sistema[col_importe_sistema].apply(normalizar_importe)
    df_sistema['Desc_norm'] = df_sistema[col_desc_sistema].astype(str).str.upper().str.strip()
    if exigir_cuit and col_cuit_banco and col_cuit_sistema:
        df_banco['CUIT_norm'] = df_banco[col_cuit_banco].astype(str).str.replace(r'[-\s]', '', regex=True)
        df_sistema['CUIT_norm'] = df_sistema[col_cuit_sistema].astype(str).str.replace(r'[-\s]', '', regex=True)
    resultados = []
    sistema_usados = set()
    for idx_b, row_b in df_banco.iterrows():
        fecha_b = row_b['Fecha_norm']
        importe_b = row_b['Importe_norm']
        desc_b = row_b['Desc_norm']
        cuit_b = row_b.get('CUIT_norm', '') if exigir_cuit else ''
        mejor_match = None
        mejor_score = -1
        for idx_s, row_s in df_sistema.iterrows():
            if idx_s in sistema_usados:
                continue
            fecha_s = row_s['Fecha_norm']
            importe_s = row_s['Importe_norm']
            desc_s = row_s['Desc_norm']
            cuit_s = row_s.get('CUIT_norm', '') if exigir_cuit else ''
            if pd.isna(fecha_b) or pd.isna(fecha_s):
                continue
            diff_dias = abs((fecha_b - fecha_s).days)
            if diff_dias > tolerancia_dias:
                continue
            if importe_s == 0:
                continue
            diff_pct = abs(importe_b - importe_s) / abs(importe_s)
            if diff_pct > tolerancia_pct:
                continue
            score = 0
            if diff_dias == 0: score += 10
            if diff_pct == 0: score += 10
            if desc_b and desc_s and any(p in desc_s for p in desc_b.split() if len(p) > 3):
                score += 5
            if exigir_cuit and cuit_b and cuit_s and cuit_b == cuit_s:
                score += 20
            if score > mejor_score:
                mejor_score = score
                mejor_match = idx_s
        if mejor_match is not None:
            sistema_usados.add(mejor_match)
            row_s = df_sistema.loc[mejor_match]
            resultados.append({
                'Fecha': fecha_b,
                'Concepto_Banco': desc_b,
                'Importe_Banco': importe_b,
                'Concepto_Sistema': row_s['Desc_norm'],
                'Importe_Sistema': row_s['Importe_norm'],
                'Diferencia': abs(importe_b - row_s['Importe_norm']),
                'Estado': 'CONCILIADO',
                'Dias_Diff': abs((fecha_b - row_s['Fecha_norm']).days) if pd.notna(fecha_b) and pd.notna(row_s['Fecha_norm']) else None
            })
        else:
            resultados.append({
                'Fecha': fecha_b,
                'Concepto_Banco': desc_b,
                'Importe_Banco': importe_b,
                'Concepto_Sistema': None,
                'Importe_Sistema': None,
                'Diferencia': None,
                'Estado': 'PENDIENTE',
                'Dias_Diff': None
            })
    for idx_s, row_s in df_sistema.iterrows():
        if idx_s not in sistema_usados:
            resultados.append({
                'Fecha': row_s['Fecha_norm'],
                'Concepto_Banco': None,
                'Importe_Banco': None,
                'Concepto_Sistema': row_s['Desc_norm'],
                'Importe_Sistema': row_s['Importe_norm'],
                'Diferencia': None,
                'Estado': 'SIN_MOVIMIENTO_BANCO',
                'Dias_Diff': None
            })
    return pd.DataFrame(resultados)

def conciliar_agregado(df_banco, df_sistema, col_fecha_banco, col_importe_banco, col_desc_banco,
                       col_fecha_sistema, col_importe_sistema,
                       tolerancia_pct=0.0, tolerancia_dias=0):
    df_banco = df_banco.copy()
    df_sistema = df_sistema.copy()
    df_banco['Fecha_norm'] = df_banco[col_fecha_banco].apply(normalizar_fecha)
    df_banco['Importe_norm'] = df_banco[col_importe_banco].apply(normalizar_importe)
    df_banco['Desc_norm'] = df_banco[col_desc_banco].astype(str).str.upper().str.strip()
    df_sistema['Fecha_norm'] = df_sistema[col_fecha_sistema].apply(normalizar_fecha)
    df_sistema['Importe_norm'] = df_sistema[col_importe_sistema].apply(normalizar_importe)
    sistema_agrup = df_sistema.groupby(df_sistema['Fecha_norm'].dt.date)['Importe_norm'].sum().reset_index()
    sistema_agrup.columns = ['Fecha', 'Importe_Sistema']
    resultados = []
    sistema_usados = set()
    for idx_b, row_b in df_banco.iterrows():
        fecha_b = row_b['Fecha_norm']
        importe_b = row_b['Importe_norm']
        desc_b = row_b['Desc_norm']
        if pd.isna(fecha_b):
            continue
        fecha_b_date = fecha_b.date()
        mejor_match = None
        mejor_score = -1
        for idx_s, row_s in sistema_agrup.iterrows():
            if idx_s in sistema_usados:
                continue
            fecha_s = row_s['Fecha']
            importe_s = row_s['Importe_Sistema']
            if fecha_s is None or pd.isna(fecha_s):
                continue
            diff_dias = abs((fecha_b_date - fecha_s).days if hasattr(fecha_b_date, 'days') else abs((pd.Timestamp(fecha_b_date) - pd.Timestamp(fecha_s)).days))
            if diff_dias > tolerancia_dias:
                continue
            if importe_s == 0:
                continue
            diff_pct = abs(importe_b - importe_s) / abs(importe_s)
            if diff_pct > tolerancia_pct:
                continue
            score = 0
            if diff_dias == 0: score += 10
            if diff_pct == 0: score += 10
            if score > mejor_score:
                mejor_score = score
                mejor_match = idx_s
        if mejor_match is not None:
            sistema_usados.add(mejor_match)
            row_s = sistema_agrup.loc[mejor_match]
            resultados.append({
                'Fecha': fecha_b,
                'Concepto_Banco': desc_b,
                'Importe_Banco': importe_b,
                'Concepto_Sistema': f'Agregado dia {row_s["Fecha"]}',
                'Importe_Sistema': row_s['Importe_Sistema'],
                'Diferencia': abs(importe_b - row_s['Importe_Sistema']),
                'Estado': 'CONCILIADO (agregado)',
                'Dias_Diff': abs((pd.Timestamp(fecha_b_date) - pd.Timestamp(row_s['Fecha'])).days)
            })
        else:
            resultados.append({
                'Fecha': fecha_b,
                'Concepto_Banco': desc_b,
                'Importe_Banco': importe_b,
                'Concepto_Sistema': None,
                'Importe_Sistema': None,
                'Diferencia': None,
                'Estado': 'PENDIENTE',
                'Dias_Diff': None
            })
    for idx_s, row_s in sistema_agrup.iterrows():
        if idx_s not in sistema_usados:
            resultados.append({
                'Fecha': row_s['Fecha'],
                'Concepto_Banco': None,
                'Importe_Banco': None,
                'Concepto_Sistema': f'Agregado dia {row_s["Fecha"]}',
                'Importe_Sistema': row_s['Importe_Sistema'],
                'Diferencia': None,
                'Estado': 'SIN_MOVIMIENTO_BANCO',
                'Dias_Diff': None
            })
    return pd.DataFrame(resultados)
