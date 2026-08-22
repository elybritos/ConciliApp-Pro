# -*- coding: utf-8 -*-
"""
motor_conciliacion.py

Motor de conciliacion bancaria generico.
Mejorado para archivos reales con encabezados en cualquier fila,
columnas vacias, metadata, multiples paginas, etc.
"""

import re
import io
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── Palabras clave para detectar encabezados ──────────────────────────────
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

# ── Patrones para detectar filas de metadata ─────────────────────────────
PATRONES_METADATA = [
    r'^fecha de descarga', r'^empresa:', r'^operador:', r'^filtrado por:',
    r'^página \d+ de \d+', r'^total:', r'^listado de', r'^hc latinoamerica',
    r'^desde\s+\d', r'^hasta\s+\d', r'^sucursal:', r'^cobrador:',
    r'^cliente:', r'^\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}$',
]

# ── Firmas de bancos para deteccion automatica ───────────────────────────
FIRMAS_BANCOS = {
    'Banco Galicia': {
        'columnas': ['fecha', 'concepto', 'debito', 'credito', 'saldo'],
        'patrones_texto': ['galicia', 'cbu', 'sucursal'],
    },
    'Banco Santander': {
        'columnas': ['fecha', 'descripcion', 'debitos', 'creditos', 'saldo'],
        'patrones_texto': ['santander', 'rio'],
    },
    'Banco BBVA': {
        'columnas': ['fecha', 'concepto', 'debe', 'haber', 'saldo'],
        'patrones_texto': ['bbva', 'frances'],
    },
    'Banco Nacion': {
        'columnas': ['fecha', 'concepto', 'debito', 'credito', 'saldo'],
        'patrones_texto': ['nacion', 'bna'],
    },
    'Banco Provincia': {
        'columnas': ['fecha', 'descripcion', 'debito', 'credito'],
        'patrones_texto': ['provincia', 'bapro'],
    },
    'Mercado Pago': {
        'columnas': ['fecha', 'descripcion', 'monto', 'estado'],
        'patrones_texto': ['mercado pago', 'mp', 'mercadopago', 'operacion'],
    },
    'Tarjeta Naranja': {
        'columnas': ['fecha', 'descripcion', 'monto', 'cuotas'],
        'patrones_texto': ['naranja', 'tarjeta'],
    },
    'Visa / Mastercard': {
        'columnas': ['fecha', 'descripcion', 'monto', 'cupon'],
        'patrones_texto': ['visa', 'mastercard', 'cupon', 'liquidacion'],
    },
}


def normalizar_texto(t):
    if pd.isna(t): return ''
    t = re.sub(r'[.,]', ' ', str(t))
    return re.sub(r'\s+', ' ', t).strip().upper()


def normalizar_importe(val):
    """Normaliza un importe a float."""
    if pd.isna(val): return 0.0

    s = str(val).strip()
    negativo = False
    if s.startswith('(') and s.endswith(')'):
        negativo = True
        s = s[1:-1]

    s = re.sub(r'[$\u20ac\u00a3\s]', '', s)

    if not s:
        return 0.0

    num_commas = s.count(',')
    num_dots = s.count('.')

    if num_dots >= 1 and num_commas == 1 and s.rfind(',') > s.rfind('.'):
        s = s.replace('.', '').replace(',', '.')
    elif num_commas >= 1 and num_dots == 1 and s.rfind('.') > s.rfind(','):
        s = s.replace(',', '')
    elif num_commas == 1 and num_dots == 0:
        s = s.replace(',', '.')
    elif num_dots >= 2 and num_commas == 0:
        s = s.replace('.', '')

    try:
        resultado = float(s)
        return -resultado if negativo else resultado
    except:
        return 0.0


def normalizar_fecha(val):
    """Intenta parsear fechas. Maneja numeros de serie de Excel y texto."""
    if pd.isna(val): return pd.NaT

    if isinstance(val, (datetime, pd.Timestamp)):
        return pd.Timestamp(val)

    if isinstance(val, (int, float)) and val > 30000:
        try:
            return pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(val))
        except:
            pass

    s = str(val).strip()
    if not s or s.lower() in ['nan', 'nat', 'none', '']:
        return pd.NaT

    try:
        num = float(s)
        if num > 30000:
            return pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(num))
    except:
        pass

    formatos = [
        '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
        '%Y/%m/%d', '%Y-%m-%d', '%m/%d/%Y',
        '%d.%m.%Y', '%d.%m.%y',
    ]

    for fmt in formatos:
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            continue

    try:
        return pd.to_datetime(val, dayfirst=True, errors='coerce')
    except:
        return pd.NaT


def _es_fila_metadata(fila):
    """Detecta si una fila es metadata (no datos)."""
    texto_completo = ' '.join([str(c).strip() for c in fila if pd.notna(c)]).lower()
    for patron in PATRONES_METADATA:
        if re.search(patron, texto_completo):
            return True
    return False


def _es_excel(bytes_data):
    """Detecta si los bytes corresponden a un archivo Excel."""
    return bytes_data[:4] == b'PK\x03\x04' or bytes_data[:4] == b'\xd0\xcf\x11\xe0'


def _leer_como_excel(bytes_data, header, nrows=None):
    kwargs = {'header': header}
    if nrows is not None:
        kwargs['nrows'] = nrows
    try:
        return pd.read_excel(io.BytesIO(bytes_data), **kwargs)
    except Exception:
        return pd.read_excel(io.BytesIO(bytes_data), engine='xlrd', **kwargs)


def _leer_como_csv(bytes_data, header, nrows=None):
    kwargs = {'sep': None, 'engine': 'python', 'header': header}
    if nrows is not None:
        kwargs['nrows'] = nrows

    for encoding in ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']:
        try:
            kwargs['encoding'] = encoding
            return pd.read_csv(io.BytesIO(bytes_data), **kwargs)
        except Exception:
            continue
    raise ValueError("No se pudo leer el archivo como CSV.")


def _puntaje_fila_encabezado(fila):
    """Calcula un puntaje para una fila candidata a ser encabezado."""
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


def detectar_fila_encabezado(bytes_data, max_filas=20):
    """Detecta la fila de encabezados. Retorna (fila_encabezado, df_raw)."""
    es_excel = _es_excel(bytes_data)

    if es_excel:
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


def _columna_es_numerica_importe(df, col):
    """Verifica si una columna parece contener importes numericos."""
    if col not in df.columns:
        return 0
    col_data = df[col].dropna()
    if len(col_data) == 0:
        return 0
    convertidos = col_data.apply(normalizar_importe)
    no_cero = (convertidos != 0).sum()
    return no_cero


def _columna_es_fecha(df, col):
    """Verifica si una columna parece contener fechas."""
    if col not in df.columns:
        return 0
    col_data = df[col].dropna()
    if len(col_data) == 0:
        return 0
    convertidos = col_data.apply(normalizar_fecha)
    validas = convertidos.notna().sum()
    return validas


def _columna_es_texto_largo(df, col):
    """Verifica si una columna parece contener textos descriptivos."""
    if col not in df.columns:
        return 0
    col_data = df[col].dropna().astype(str)
    if len(col_data) == 0:
        return 0
    longitudes = col_data.apply(len)
    return longitudes.mean()


def limpiar_dataframe(df):
    """
    Limpia un DataFrame despues de leerlo:
    - Elimina columnas vacias
    - Elimina filas de metadata
    - Elimina filas totalmente vacias
    """
    if df.empty:
        return df
    df = df.dropna(axis=1, how='all')
    df = df.dropna(how='all')
    filas_validas = []
    for idx, fila in df.iterrows():
        if not _es_fila_metadata(fila):
            filas_validas.append(idx)
    df = df.loc[filas_validas].reset_index(drop=True)
    return df


def leer_archivo(bytes_data, fila_encabezado=None):
    """Lee un archivo Excel o CSV con limpieza automatica."""
    if fila_encabezado is None:
        fila_encabezado, _ = detectar_fila_encabezado(bytes_data)

    es_excel = _es_excel(bytes_data)

    if es_excel:
        df = _leer_como_excel(bytes_data, header=fila_encabezado)
    else:
        df = _leer_como_csv(bytes_data, header=fila_encabezado)

    df.columns = [str(c).strip() if c is not None else f'Col_{i}'
                  for i, c in enumerate(df.columns)]
    df = limpiar_dataframe(df)

    filas_a_mantener = []
    for idx, fila in df.iterrows():
        es_meta = False
        for val in fila:
            if pd.notna(val):
                v_str = str(val).strip().lower()
                if any(re.search(p, v_str) for p in PATRONES_METADATA):
                    es_meta = True
                    break
        if not es_meta:
            filas_a_mantener.append(idx)

    df = df.loc[filas_a_mantener].reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════════════
# DETECCION DE BANCO
# ═══════════════════════════════════════════════════════════════════════

def detectar_banco(df):
    """Detecta el banco/origin del archivo por sus columnas y contenido."""
    columnas_norm = [normalizar_texto(c) for c in df.columns]
    texto_muestra = ' '.join(columnas_norm).lower()

    for idx in range(min(5, len(df))):
        fila_texto = ' '.join([str(v).lower() for v in df.iloc[idx] if pd.notna(v)])
        texto_muestra += ' ' + fila_texto

    mejor_banco = 'Desconocido'
    mejor_score = 0

    for banco, firma in FIRMAS_BANCOS.items():
        score = 0
        for col_firma in firma['columnas']:
            col_firma_norm = normalizar_texto(col_firma)
            for col_real in columnas_norm:
                if col_firma_norm in col_real or col_real in col_firma_norm:
                    score += 3
                    break
        for patron in firma['patrones_texto']:
            if patron.lower() in texto_muestra:
                score += 2

        if score > mejor_score:
            mejor_score = score
            mejor_banco = banco

    return mejor_banco if mejor_score >= 3 else 'Banco no detectado'


def _puntaje_coincidencia(col_norm, p_norm):
    """Calcula un puntaje de coincidencia entre nombre de columna y patron."""
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
    """Detecta la columna que MEJOR coincide con alguno de los patrones."""
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


def detectar_columnas_recomendadas(df):
    """
    Detecta todas las columnas recomendadas.
    Si la deteccion por nombre falla, usa deteccion por contenido.
    """
    result = {
        'fecha': detectar_columna(df, PALABRAS_CLAVE_FECHA),
        'importe': detectar_columna(df, PALABRAS_CLAVE_IMPORTE),
        'concepto': detectar_columna(df, PALABRAS_CLAVE_CONCEPTO),
        'cuit': detectar_columna(df, PALABRAS_CLAVE_CUIT),
    }

    if result['importe'] is None or _columna_es_numerica_importe(df, result['importe']) == 0:
        mejor_col = None
        mejor_count = 0
        for col in df.columns:
            count = _columna_es_numerica_importe(df, col)
            if count > mejor_count:
                if result['fecha'] and col == result['fecha']:
                    continue
                mejor_count = count
                mejor_col = col
        if mejor_col and mejor_count > 0:
            result['importe'] = mejor_col

    if result['fecha'] is None or _columna_es_fecha(df, result['fecha']) == 0:
        mejor_col = None
        mejor_count = 0
        for col in df.columns:
            count = _columna_es_fecha(df, col)
            if count > mejor_count:
                mejor_count = count
                mejor_col = col
        if mejor_col and mejor_count > 0:
            result['fecha'] = mejor_col

    if result['concepto'] is None or _columna_es_texto_largo(df, result['concepto']) < 5:
        mejor_col = None
        mejor_len = 0
        for col in df.columns:
            if result['fecha'] and col == result['fecha']:
                continue
            if result['importe'] and col == result['importe']:
                continue
            avg_len = _columna_es_texto_largo(df, col)
            if avg_len > mejor_len:
                mejor_len = avg_len
                mejor_col = col
        if mejor_col and mejor_len > 5:
            result['concepto'] = mejor_col

    return result


def diagnosticar_columna(df, col_nombre, tipo='fecha'):
    """Diagnostica una columna especifica."""
    if col_nombre is None or col_nombre not in df.columns:
        return {'error': 'Columna no encontrada'}

    col = df[col_nombre]
    total = len(col)
    no_nulos = col.notna().sum()

    if tipo == 'fecha':
        parseadas = col.apply(normalizar_fecha)
        validas = parseadas.notna().sum()
        ejemplos_validos = parseadas.dropna().head(3).tolist()
        ejemplos_invalidos = col[parseadas.isna() & col.notna()].head(3).tolist()
        return {
            'total': total,
            'no_nulos': int(no_nulos),
            'validas': int(validas),
            'tasa': round(validas/total*100, 1) if total > 0 else 0,
            'ejemplos_validos': [str(v) for v in ejemplos_validos],
            'ejemplos_invalidos': [str(v) for v in ejemplos_invalidos],
        }

    elif tipo == 'importe':
        parseados = col.apply(normalizar_importe)
        no_cero = (parseados != 0).sum()
        ejemplos = col.head(5).tolist()
        parseados_ej = parseados.head(5).tolist()
        return {
            'total': total,
            'no_nulos': int(no_nulos),
            'no_cero': int(no_cero),
            'tasa': round(no_cero/total*100, 1) if total > 0 else 0,
            'ejemplos_crudos': [str(v) for v in ejemplos],
            'ejemplos_parseados': [str(v) for v in parseados_ej],
            'suma_total': round(parseados.sum(), 2),
        }

    return {}


def conciliar(df_banco, df_sistema, col_fecha_banco, col_importe_banco, col_desc_banco,
              col_fecha_sistema, col_importe_sistema, col_desc_sistema,
              col_cuit_banco=None, col_cuit_sistema=None,
              tolerancia_pct=0.0, tolerancia_dias=0, exigir_cuit=False):
    """Conciliacion 1 a 1 con tolerancias."""
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
    """Conciliacion agregada."""
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
