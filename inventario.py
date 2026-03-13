import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="KS CLOTHING - SISTEMA INTEGRAL", layout="wide")

# --- VARIABLES FIJAS (Para evitar errores de base de datos) ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL", "XXL"]
CATEGORIAS = ["Hoodies", "Polos", "Pantalones", "Gorras", "Accesorios"]

# --- CONEXIÓN PERMANENTE ---
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    """Crea las tablas de datos si no existen."""
    try:
        with conn.session as s:
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, categoria TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, categoria TEXT, talla TEXT, cantidad INTEGER, precio FLOAT, fecha DATE)'))
            s.commit()
    except:
        pass

inicializar_db()

# --- FUNCIONES DE LECTURA SEGURA ---
def leer_datos(query):
    try:
        return conn.query(query, ttl=0)
    except:
        return pd.DataFrame()

def obtener_stock_almacen():
    df_in = leer_datos('SELECT producto, talla, SUM(cantidad) as t_in FROM ingresos GROUP BY producto, talla')
    df_out = leer_datos('SELECT producto, talla, SUM(cantidad) as t_out FROM distribucion GROUP BY producto, talla')
    
    if df_in.empty:
        return pd.DataFrame(columns=['producto', 'talla', 'Disponible'])
    
    df = pd.merge(df_in, df_out, on=['producto', 'talla'], how='left').fillna(0)
    df['Disponible'] = df['t_in'] - df['t_out']
    return df[df['Disponible'] > 0]

# --- CONTROL DE ACCESO ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False

if not st.session_state.logueado:
    st.title("🔐 Acceso KS CLOTHING")
    col1, col2 = st.columns(2)
    with col1:
        pin = st.text_input("Ingrese PIN de Seguridad", type="password")
        if st.button("Entrar al Sistema"):
            if pin == "2026":
                st.session_state.logueado = True
                st.session_state.rol = "Administrador"
                st.rerun()
            elif pin == "1234":
                st.session_state.logueado = True
                st.session_state.rol = "Tienda"
                st.rerun()
            else:
                st.error("PIN Incorrecto")
else:
    # --- MENÚ PRINCIPAL ---
    st.sidebar.title(f"👤 {st.session_state.rol}")
    
    if st.session_state.rol == "Administrador":
        menu = ["📊 Dashboard", "📥 Almacén Central", "🚚 Enviar a Tiendas", "💰 Registrar Venta", "📜 Historial General", "⚙️ Ajustes"]
    else:
        menu = ["💰 Registrar Venta", "📊 Mi Stock"]
        
    choice = st.sidebar.radio("Navegación", menu)

    # --- PÁGINA: DASHBOARD ---
    if choice == "📊 Dashboard":
        st.header("📊 Panel de Control General")
        df_stock = obtener_stock_almacen()
        
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Prendas en Almacén", int(df_stock['Disponible'].sum()) if not df_stock.empty else 0)
        
        df_v = leer_datos("SELECT SUM(precio) as total FROM ventas")
        total_v = df_v['total'].iloc[0] if not df_v.empty and df_v['total'].iloc[0] is not None else 0
        with c2: st.metric("Ventas Totales", f"S/. {total_v:.2f}")
        
        if not df_stock.empty:
            fig = px.bar(df_stock, x="producto", y="Disponible", color="talla", title="Stock por Modelo y Talla")
            st.plotly_chart(fig, use_container_width=True)

    # --- PÁGINA: ALMACÉN ---
    elif choice == "📥 Almacén Central":
        st.header("📥 Ingreso de Mercadería")
        with st.form("form_ingreso", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                p = st.text_input("Nombre del Producto").upper()
                cat = st.selectbox("Categoría", CATEGORIAS)
            with col2:
                t = st.selectbox("Talla", TALLAS)
                can = st.number_input("Cantidad", min_value=1)
            
            if st.form_submit_button("Confirmar Ingreso"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ingresos (producto, categoria, talla, cantidad, fecha) VALUES (:p, :cat, :t, :can, :f)"),
                              {"p":p, "cat":cat, "t":t, "can":can, "f":datetime.now().date()})
                    s.commit()
                st.success(f"Registrado: {can} unidades de {p}")

    # --- PÁGINA: DISTRIBUCIÓN ---
    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Distribución a Sucursales")
        df_s = obtener_stock_almacen()
        if df_s.empty:
            st.warning("No hay stock en almacén.")
        else:
            with st.form("form_dist"):
                prod_sel = st.selectbox("Producto", df_s['producto'].unique())
                talla_sel = st.selectbox("Talla", TALLAS)
                tienda_dest = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                cant_env = st.number_input("Cantidad", min_value=1)
                
                if st.form_submit_button("Enviar Mercadería"):
                    with conn.session as s:
                        s.execute(text("INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (:p, :t, :c, :ti, :f)"),
                                  {"p":prod_sel, "t":talla_sel, "c":cant_env, "ti":tienda_dest, "f":datetime.now().date()})
                        s.commit()
                    st.success("Envío registrado correctamente.")

    # --- PÁGINA: VENTAS ---
    elif choice == "💰 Registrar Venta":
        st.header("💰 Registro de Venta Diaria")
        with st.form("form_ventas", clear_on_submit=True):
            tienda_v = st.selectbox("Tienda", NOMBRES_TIENDAS)
            prod_v = st.text_input("Producto").upper()
            col1, col2 = st.columns(2)
            with col1:
                talla_v = st.selectbox("Talla", TALLAS)
                cant_v = st.number_input("Cantidad", min_value=1)
            with col2:
                precio_v = st.number_input("Precio Total de Venta (S/.)", min_value=0.0)
            
            if st.form_submit_button("Guardar Venta"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ventas (tienda, producto, talla, cantidad, precio, fecha) VALUES (:ti, :p, :t, :c, :pr, :f)"),
                              {"ti":tienda_v, "p":prod_v, "t":talla_v, "c":cant_v, "pr":precio_v, "f":datetime.now().date()})
                    s.commit()
                st.success("Venta guardada.")

    # --- PÁGINA: HISTORIAL ---
    elif choice == "📜 Historial General":
        st.header("📜 Movimientos Registrados")
        t1, t2, t3 = st.tabs(["📥 Ingresos", "🚚 Envíos", "💰 Ventas"])
        with t1: st.dataframe(leer_datos("SELECT * FROM ingresos ORDER BY fecha DESC"), use_container_width=True)
        with t2: st.dataframe(leer_datos("SELECT * FROM distribucion ORDER BY fecha DESC"), use_container_width=True)
        with t3: st.dataframe(leer_datos("SELECT * FROM ventas ORDER BY fecha DESC"), use_container_width=True)

    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.logueado = False
        st.rerun()
