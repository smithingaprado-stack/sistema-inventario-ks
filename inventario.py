import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime

# --- CONFIGURACIÓN ---
# PIN para el Almacén: 2026 / PIN para Tiendas: 1234
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- BASE DE DATOS ---
conn = sqlite3.connect('ks_sistema_final.db', check_same_thread=False)
c = conn.cursor()

def crear_tablas():
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas_tiendas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    conn.commit()

crear_tablas()

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema KS - Control Total", layout="wide")

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
    # --- MENÚ SEGÚN ROL ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 Modo: ADMINISTRADOR")
        menu = ["📊 Dashboard Global", "📥 Ingreso Almacén", "🚚 Envío a Tiendas", "📝 Ver Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 Modo: TIENDA")
        menu = ["🛒 Registrar Venta Diaria", "📝 Hacer Pedido al Almacén"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # --- LÓGICA DE TIENDA (BLOQUEADA) ---
    if choice == "🛒 Registrar Venta Diaria":
        st.header("🛒 Registrar Venta de la Tienda")
        with st.form("venta"):
            tienda_vende = st.selectbox("¿Qué tienda eres?", NOMBRES_TIENDAS)
            prod_v = st.text_input("Producto vendido").upper()
            talla_v = st.selectbox("Talla", TALLAS)
            cant_v = st.number_input("Cantidad vendida", min_value=1)
            if st.form_submit_button("Registrar Venta"):
                c.execute('INSERT INTO ventas_tiendas (tienda, producto, talla, cantidad, fecha) VALUES (?,?,?,?,?)',
                          (tienda_vende, prod_v, talla_v, cant_v, datetime.now().date()))
                conn.commit()
                st.success("Venta registrada y descontada del reporte.")

    elif choice == "📝 Hacer Pedido al Almacén":
        st.header("📝 Solicitar Mercadería")
        with st.form("pedido"):
            t_ped = st.selectbox("Tienda", NOMBRES_TIENDAS)
            msg = st.text_area("Listado de lo que falta")
            img = st.file_uploader("Subir foto de la lista", type=['jpg', 'png'])
            if st.form_submit_button("Enviar al Almacén Central"):
                img_bytes = img.read() if img else None
                c.execute('INSERT INTO pedidos (tienda, pedido_texto, foto, fecha) VALUES (?,?,?,?)',
                          (t_ped, msg, img_bytes, datetime.now()))
                conn.commit()
                st.success("¡Pedido enviado con éxito!")

    # --- LÓGICA DE ADMINISTRADOR (CONTROL TOTAL) ---
    elif choice == "📊 Dashboard Global":
        st.header("📊 Resumen General")
        # Aquí se mostraría el inventario total menos lo que las tiendas vendieron
        st.write("Aquí verás el stock central y lo que cada tienda ha vendido.")
        df_v = pd.read_sql('SELECT * FROM ventas_tiendas', conn)
        st.subheader("Ventas Recientes por Tienda")
        st.dataframe(df_v)

    elif choice == "📝 Ver Pedidos Recibidos":
        st.header("📦 Pedidos de las Tiendas")
        pedidos = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn)
        for i, r in pedidos.iterrows():
            with st.expander(f"Pedido de {r['tienda']} - {r['fecha']}"):
                st.write(r['pedido_texto'])
                if r['foto']: st.image(r['foto'], width=300)
                if st.button(f"Atendido #{r['id']}"):
                    c.execute('DELETE FROM pedidos WHERE id=?', (r['id'],))
                    conn.commit()
                    st.rerun()

    # Opción para cerrar sesión
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()