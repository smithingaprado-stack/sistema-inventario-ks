import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import plotly.express as px

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="KS CLOTHING - SISTEMA INTEGRAL", layout="wide")

# --- VARIABLES ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL", "XXL"]
CATEGORIAS = ["Hoodies", "Polos", "Pantalones", "Gorras"]

# --- CONEXIÓN ---
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    try:
        with conn.session as s:
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, categoria TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, precio FLOAT, fecha DATE)'))
            s.commit()
    except:
        pass

inicializar_db()

# --- FUNCIONES DE SEGURIDAD PARA LEER ---
def leer_tabla(query):
    try:
        return conn.query(query, ttl=0)
    except:
        return pd.DataFrame()

# --- LÓGICA DE STOCK ---
def obtener_stock_central():
    df_in = leer_tabla('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla')
    df_dist = leer_tabla('SELECT producto, talla, SUM(cantidad) as total_dist FROM distribucion GROUP BY producto, talla')
    
    if df_in.empty: return pd.DataFrame(columns=['producto', 'talla', 'Stock Almacén'])
    
    if df_dist.empty:
        df_in['Stock Almacén'] = df_in['total_in']
        return df_in
        
    df = pd.merge(df_in, df_dist, on=['producto', 'talla'], how='left').fillna(0)
    df['Stock Almacén'] = df['total_in'] - df['total_dist']
    return df[df['Stock Almacén'] > 0]

# --- INTERFAZ ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acceso KS CLOTHING")
    pin = st.text_input("PIN de Seguridad", type="password")
    if st.button("Entrar"):
        if pin == "2026":
            st.session_state.autenticado = True
            st.rerun()
        else: st.error("PIN Incorrecto")
else:
    menu = st.sidebar.radio("Menú Principal", ["📊 Dashboard", "📥 Almacén", "🚚 Enviar a Tiendas", "💰 Ventas", "📜 Historial Completo"])

    if menu == "📊 Dashboard":
        st.header("📊 Panel de Control")
        df_s = obtener_stock_central()
        if not df_s.empty:
            fig = px.pie(df_s, values='Stock Almacén', names='producto', title="Distribución de Productos")
            st.plotly_chart(fig)
            st.dataframe(df_s, use_container_width=True)
        else: st.info("No hay datos para mostrar gráficos aún.")

    elif menu == "📥 Almacén":
        st.subheader("📥 Cargar nueva mercadería")
        with st.form("ing"):
            p = st.text_input("Producto").upper()
            cat = st.selectbox("Categoría", CATEGORIAS)
            t = st.selectbox("Talla", TALLAS)
            c = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar Ingreso"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ingresos (producto, categoria, talla, cantidad, fecha) VALUES (:p, :cat, :t, :c, :f)"),
                              {"p":p, "cat":cat, "t":t, "c":c, "f":datetime.now().date()})
                    s.commit()
                st.success("Guardado"); st.rerun()

    elif menu == "💰 Ventas":
        st.subheader("💰 Registro de Ventas")
        with st.form("vta"):
            ti = st.selectbox("Tienda", NOMBRES_TIENDAS)
            pr = st.text_input("Producto").upper()
            ta = st.selectbox("Talla", TALLAS)
            can = st.number_input("Cantidad", min_value=1)
            pre = st.number_input("Precio Total S/.", min_value=0.0)
            if st.form_submit_button("Registrar Venta"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ventas (tienda, producto, talla, cantidad, precio, fecha) VALUES (:ti, :p, :t, :c, :pr, :f)"),
                              {"ti":ti, "p":pr, "t":ta, "c":can, "pr":pre, "f":datetime.now().date()})
                    s.commit()
                st.success("Venta registrada")

    elif menu == "📜 Historial Completo":
        st.header("📜 Historial de Movimientos")
        t1, t2, t3 = st.tabs(["Ingresos", "Envíos", "Ventas"])
        with t1: st.write(leer_tabla("SELECT * FROM ingresos"))
        with t2: st.write(leer_tabla("SELECT * FROM distribucion"))
        with t3: st.write(leer_tabla("SELECT * FROM ventas"))

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()
