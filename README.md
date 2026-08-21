# 📊 ConciliApp PRO

Conciliacion bancaria inteligente con login de usuarios, perfiles guardados e historial.

---

## 🚀 Como empezar (3 pasos)

### Paso 1: Instalar Python
Si no tenes Python instalado, descargalo de https://python.org (version 3.10 o superior).

### Paso 2: Instalar dependencias
Abri la terminal (CMD en Windows) en esta carpeta y ejecuta:

```bash
pip install -r requirements.txt
```

Esto instala todo lo necesario (Streamlit, Pandas, Plotly, etc.).

### Paso 3: Correr la app
En la misma terminal:

```bash
streamlit run app.py
```

Se abrira automaticamente en tu navegador en http://localhost:8501

---

## 🔐 Primer uso

1. **Registrate** con un usuario y contraseña (pestaña "Registrarse")
2. **Inicia sesion** con esas credenciales
3. **Subi tus archivos** del banco y del sistema contable
4. **Configura las columnas** (la app detecta automaticamente, pero revisalas)
5. **Guarda un perfil** con nombre para la proxima vez
6. **Ejecuta la conciliacion**

---

## 📁 Archivos incluidos

| Archivo | Que hace |
|---------|----------|
| `app.py` | Interfaz web de la aplicacion |
| `database.py` | Base de datos local (SQLite) |
| `motor_conciliacion.py` | Motor de conciliacion bancaria |
| `requirements.txt` | Lista de dependencias |
| `conciliapp.db` | Se crea automaticamente al primer uso |

---

## 💡 Tips

- **Perfiles**: La primera vez configura todo y guarda un perfil. La proxima solo seleccionalo del dropdown.
- **Tolerancias**: Si no concilia todo, proba aumentar la tolerancia de dias (para acreditaciones demoradas) o de importe (para comisiones de Posnet).
- **Modo Agregado**: Si tenes muchos movimientos por dia (cierre de caja, Mercado Pago), usa "Agregado" en vez de "1 a 1".
- **Formatos soportados**: Excel (.xlsx, .xls) y CSV. Los archivos pueden tener titulos, logos o info extra en las primeras filas.

---

## ⚠️ Nota importante

Tus datos **nunca salen de tu computadora**. Todo se procesa localmente. La base de datos SQLite se guarda en esta misma carpeta.

---

ConciliApp PRO (c) 2026
