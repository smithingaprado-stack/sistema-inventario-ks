import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# --- CONFIGURACIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- CONEXIÓN PERMANENTE ---
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    """Crea las tablas si no existen para evitar el error de OperationalError."""
    try:
        with conn.session as s:
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.commit()
    except Exception as e:
        st.error(f"Error al conectar/crear tablas: {e}")

# Ejecutamos la creación de tablas al iniciar
inicializar_db()

# --- FUNCIONES DE DATOS ---
def obtener_stock_real():
    try:
        df_in = conn.query('SELECT producto, talla, SUM(cantidad) as t_in FROM ingresos GROUP BY producto, talla')
        df_out = conn.query('SELECT producto, talla, SUM(cantidad) as t_out FROM distribucion GROUP BY producto, talla')
        
        if df_in.empty:
            return pd.DataFrame(columns=['producto', 'talla', 'Disponible'])
        
        df = pd.merge(df_in, df_out, on=['producto', 'talla'], how='left').fillna(0)
        df['Disponible'] = df['t_in'] - df['t_out']
        return df[df['Disponible'] > 0]
    except:
        # Si las tablas están recién creadas y vacías, devolvemos un DataFrame vacío
        return pd.DataFrame(columns=['producto', 'talla', 'Disponible'])

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema KS - Control Total", layout="wide")

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso Sistema KS")
    pin = st.text_input("Introduce tu PIN", type="password")
    if st.button("Ingresar"):
        if pin == "2026":
            st.session_state['rol'] = "admin"; st.rerun()
        elif pin == "1234":
            st.session_state['rol'] = "tienda"; st.rerun()
        else:
            st.error("PIN Incorrecto")
else:
    # MENÚ
    menu = ["📊 Stock Real", "📥 Cargar Stock", "🛒 Registrar Venta"] if st.session_state['rol'] == "admin" else ["🛒 Registrar Venta"]
    choice = st.sidebar.selectbox("Menú", menu)

    if choice == "📊 Stock Real":
        st.header("📊 Stock Real en Almacén")
        df = obtener_stock_real()
        if df.empty:
            st.info("No hay mercadería registrada todavía.")
        else:
            st.dataframe(df, use_container_width=True)

    elif choice == "📥 Cargar Stock":
        st.header("📥 Ingreso de Mercadería")
        with st.form("in", clear_on_submit=True):
            p = st.text_input("Producto").upper(); t = st.selectbox("Talla", TALLAS); c = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar en Almacén"):
                with conn.session as s:
                    s.execute(text('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (:p, :t, :c, :f)'),
                              {"p":p, "t":t, "c":c, "f":datetime.now().date()})
                    s.commit()
                st.success("✅ Guardado correctamente en la base de datos.")
                st.rerun()

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
