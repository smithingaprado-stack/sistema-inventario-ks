import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime

# --- CONFIGURACIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- BASE DE DATOS (Ruta compatible con la nube) ---
conn = sqlite3.connect('ks_data.db', check_same_thread=False)
c = conn.cursor()

def crear_tablas():
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas_tiendas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    conn.commit()

crear_tablas()

# --- FUNCIONES DE APOYO ---
def obtener_stock_total():
    ingresos = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla', conn)
    salidas = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_out FROM distribucion GROUP BY producto, talla', conn)
    if ingresos.empty: return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    df = pd.merge(ingresos, salidas, on=['producto', 'talla'], how='left').fillna(0)
    df['stock_disponible'] = df['total_in'] - df['total_out']
    return df

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema KS - Web", layout="wide")

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso al Sistema KS")
    pin = st.text_input("Introduce tu PIN", type="password")
    if st.button("Ingresar"):
        if pin == "2026":
            st.session_state['rol'] = "admin"
            st.rerun()
        elif pin == "1234":
            st.session_state['rol'] = "tienda"
            st.rerun()
        else:
            st.error("PIN Incorrecto")
else:
    # --- MENÚ ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📥 Ingreso Almacén", "🚚 Envío a Tiendas", "📊 Inventario Real", "📦 Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 TIENDA")
        menu = ["🛒 Registrar Venta", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # 1. INGRESO (ADMIN)
    if choice == "📥 Ingreso Almacén":
        st.subheader("Registrar Mercadería Nueva")
        with st.form("ingreso"):
            p = st.text_input("Producto").upper()
            t = st.selectbox("Talla", TALLAS)
            c_in = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar"):
                c.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', (p, t, c_in, datetime.now().date()))
                conn.commit()
                st.success("Guardado correctamente")

    # 2. ENVÍO (ADMIN)
    elif choice == "🚚 Envío a Tiendas":
        df_s = obtener_stock_total()
        if not df_s.empty:
            with st.form("envio"):
                p_sel = st.selectbox("Producto", df_s['producto'].unique())
                t_sel = st.selectbox("Talla", TALLAS)
                tienda = st.selectbox("Destino", NOMBRES_TIENDAS)
                cant = st.number_input("Cantidad", min_value=1)
                if st.form_submit_button("Confirmar Envío"):
                    c.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (?,?,?,?,?)', (p_sel, t_sel, cant, tienda, datetime.now().date()))
                    conn.commit()
                    st.success("Enviado")
        else:
            st.warning("No hay stock disponible.")

    # 3. PEDIDOS (ADMIN)
    elif choice == "📦 Pedidos Recibidos":
        pedidos = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn)
        for i, r in pedidos.iterrows():
            with st.expander(f"De: {r['tienda']} - {r['fecha']}"):
                st.write(r['pedido_texto'])
                if r['foto']: st.image(r['foto'], width=300)
                if st.button(f"Eliminar {r['id']}"):
                    c.execute('DELETE FROM pedidos WHERE id=?', (r['id'],))
                    conn.commit()
                    st.rerun()

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
