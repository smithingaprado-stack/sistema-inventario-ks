import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime

# --- CONFIGURACIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- BASE DE DATOS ---
# Usamos una ruta simple para la nube
def get_connection():
    return sqlite3.connect('ks_database.db', check_same_thread=False)

def crear_tablas():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas_tiendas (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    conn.commit()
    conn.close()

crear_tablas()

# --- FUNCIONES DE CÁLCULO ---
def obtener_stock_real():
    conn = get_connection()
    ingresos = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla', conn)
    salidas = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_out FROM distribucion GROUP BY producto, talla', conn)
    conn.close()
    
    if ingresos.empty:
        return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    
    df = pd.merge(ingresos, salidas, on=['producto', 'talla'], how='left').fillna(0)
    df['stock_disponible'] = df['total_in'] - df['total_out']
    return df[df['stock_disponible'] > 0]

# --- INTERFAZ ---
st.set_page_config(page_title="KS - Sistema Web", layout="wide")

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso Sistema KS")
    pin = st.text_input("PIN de Acceso", type="password")
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
    # MENÚ LATERAL
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📥 Ingreso Almacén", "🚚 Enviar a Tiendas", "📊 Inventario Real", "📦 Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 TIENDA")
        menu = ["🛒 Registrar Venta", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Seleccione:", menu)

    # --- LÓGICA DE OPCIONES ---
    
    if choice == "📥 Ingreso Almacén":
        st.subheader("Entrada de Mercadería")
        with st.form("form_in", clear_on_submit=True):
            p = st.text_input("Producto").upper()
            t = st.selectbox("Talla", TALLAS)
            c_in = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Guardar Ingreso"):
                conn = get_connection()
                conn.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', 
                             (p, t, c_in, datetime.now().date()))
                conn.commit()
                conn.close()
                st.success(f"Registrado: {p} Talla {t}")

    elif choice == "🚚 Enviar a Tiendas":
        st.subheader("Distribuir a Tiendas")
        df_stock = obtener_stock_real()
        if not df_stock.empty:
            with st.form("form_out", clear_on_submit=True):
                prod_sel = st.selectbox("Producto disponible", df_stock['producto'].unique())
                talla_sel = st.selectbox("Talla", df_stock[df_stock['producto']==prod_sel]['talla'])
                tienda_dest = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                cant_env = st.number_input("Cantidad a enviar", min_value=1, step=1)
                if st.form_submit_button("Confirmar Envío"):
                    conn = get_connection()
                    conn.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (?,?,?,?,?)',
                                 (prod_sel, talla_sel, cant_env, tienda_dest, datetime.now().date()))
                    conn.commit()
                    conn.close()
                    st.success("Envío registrado")
                    st.rerun()
        else:
            st.warning("No hay productos en stock para enviar.")

    elif choice == "📊 Inventario Real":
        st.subheader("Estado Actual del Almacén (Lo que te queda)")
        df_resumen = obtener_stock_real()
        if not df_resumen.empty:
            st.dataframe(df_resumen, use_container_width=True)
        else:
            st.info("El inventario está vacío.")

    elif choice == "📝 Hacer Pedido":
        st.subheader("Enviar Pedido al Almacén")
        with st.form("form_ped", clear_on_submit=True):
            tienda_org = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            lista_txt = st.text_area("Escribe tu pedido aquí...")
            foto = st.file_uploader("O sube una foto", type=['jpg','png','jpeg'])
            if st.form_submit_button("Enviar Pedido"):
                foto_bytes = foto.read() if foto else None
                conn = get_connection()
                conn.execute('INSERT INTO pedidos (tienda, pedido_texto, foto, fecha) VALUES (?,?,?,?)',
                             (tienda_org, lista_txt, foto_bytes, datetime.now()))
                conn.commit()
                conn.close()
                st.success("🚀 Pedido enviado con éxito")

    elif choice == "📦 Pedidos Recibidos":
        st.subheader("Pedidos de las Tiendas")
        conn = get_connection()
        pedidos = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn)
        conn.close()
        for i, r in pedidos.iterrows():
            with st.expander(f"De: {r['tienda']} - {r['fecha']}"):
                st.write(r['pedido_texto'])
                if r['foto']: st.image(r['foto'])
                if st.button(f"Atendido (Borrar {r['id']})"):
                    conn = get_connection()
                    conn.execute('DELETE FROM pedidos WHERE id=?', (r['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
