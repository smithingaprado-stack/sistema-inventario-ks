import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- GESTIÓN DE BASE DE DATOS ---
def get_connection():
    # Creamos la conexión con timeout para evitar bloqueos en la nube
    return sqlite3.connect('ks_sistema_v5.db', check_same_thread=False, timeout=10)

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

# --- FUNCIONES DE LÓGICA ---
def obtener_stock_real():
    conn = get_connection()
    ingresos = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla', conn)
    salidas = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_out FROM distribucion GROUP BY producto, talla', conn)
    conn.close()
    if ingresos.empty: return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    df = pd.merge(ingresos, salidas, on=['producto', 'talla'], how='left').fillna(0)
    df['stock_disponible'] = df['total_in'] - df['total_out']
    return df

# --- INTERFAZ ---
st.set_page_config(page_title="KS - Control de Inventario", layout="wide")

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
    # --- MENÚS ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Inventario Central", "📥 Cargar Mercadería", "🚚 Enviar a Tiendas", "📦 Pedidos de Tiendas", "📈 Reporte de Ventas"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Historial y Editar", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Ir a:", menu)

    # --- FLUJO ADMINISTRADOR ---
    if choice == "📊 Inventario Central":
        st.header("📊 Stock Disponible en Almacén")
        df_resumen = obtener_stock_real()
        st.dataframe(df_resumen, use_container_width=True)

    elif choice == "📥 Cargar Mercadería":
        st.header("📥 Ingreso de Stock")
        with st.form("form_ingreso", clear_on_submit=True):
            p = st.text_input("Producto").upper()
            t = st.selectbox("Talla", TALLAS)
            c_in = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Guardar en Almacén"):
                conn = get_connection()
                conn.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', (p, t, c_in, datetime.now().date()))
                conn.commit()
                conn.close()
                st.success(f"Registrado: {p}")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Distribución a Sucursales")
        df_s = obtener_stock_real()
        if not df_s.empty:
            with st.form("form_envio", clear_on_submit=True):
                p_sel = st.selectbox("Producto", df_s['producto'].unique())
                t_sel = st.selectbox("Talla", TALLAS)
                tienda = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                cant = st.number_input("Cantidad", min_value=1, step=1)
                if st.form_submit_button("Confirmar Envío"):
                    conn = get_connection()
                    conn.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (?,?,?,?,?)', (p_sel, t_sel, cant, tienda, datetime.now().date()))
                    conn.commit()
                    conn.close()
                    st.success("Envío exitoso")
                    st.rerun()
        else:
            st.warning("No hay stock para enviar.")

    elif choice == "📦 Pedidos de Tiendas":
        st.header("📦 Pedidos Recibidos")
        conn = get_connection()
        pedidos = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn)
        conn.close()
        for i, r in pedidos.iterrows():
            with st.expander(f"Solicitud de: {r['tienda']} - {r['fecha']}"):
                st.write(f"**Detalles:** {r['pedido_texto']}")
                if r['foto']: st.image(r['foto'])
                if st.button(f"Marcar Atendido (ID {r['id']})"):
                    conn = get_connection()
                    conn.execute('DELETE FROM pedidos WHERE id=?', (r['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

    # --- FLUJO TIENDA ---
    elif choice == "🛒 Registrar Venta":
        st.header("🛒 Registro de Venta")
        with st.form("form_v", clear_on_submit=True):
            t_v = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            p_v = st.text_input("Producto").upper()
            ta_v = st.selectbox("Talla", TALLAS)
            ca_v = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Guardar Venta"):
                conn = get_connection()
                conn.execute('INSERT INTO ventas_tiendas (tienda, producto, talla, cantidad, fecha) VALUES (?,?,?,?,?)', (t_v, p_v, ta_v, ca_v, datetime.now().date()))
                conn.commit()
                conn.close()
                st.success("Venta guardada")

    elif choice == "📜 Historial y Editar":
        st.header("📜 Historial (Editar/Borrar)")
        t_sel = st.selectbox("Tienda", NOMBRES_TIENDAS)
        conn = get_connection()
        v_df = pd.read_sql(f"SELECT * FROM ventas_tiendas WHERE tienda='{t_sel}' ORDER BY id DESC", conn)
        conn.close()
        for i, r in v_df.iterrows():
            col1, col2 = st.columns([4, 1])
            col1.write(f"ID: {r['id']} | {r['producto']} | Talla {r['talla']} | Cant: {r['cantidad']}")
            if col2.button("❌ Borrar", key=f"v_{r['id']}"):
                conn = get_connection()
                conn.execute('DELETE FROM ventas_tiendas WHERE id=?', (r['id'],))
                conn.commit()
                conn.close()
                st.rerun()

    elif choice == "📝 Hacer Pedido":
        st.header("📝 Nuevo Pedido")
        with st.form("form_p", clear_on_submit=True):
            t_p = st.selectbox("Tienda", NOMBRES_TIENDAS)
            txt = st.text_area("¿Qué mercadería necesitas?")
            foto = st.file_uploader("Subir foto", type=['jpg','png'])
            if st.form_submit_button("Enviar al Almacén"):
                f_bytes = foto.read() if foto else None
                conn = get_connection()
                conn.execute('INSERT INTO pedidos (tienda, pedido_texto, foto, fecha) VALUES (?,?,?,?)', (t_p, txt, f_bytes, datetime.now()))
                conn.commit()
                conn.close()
                st.success("Pedido enviado")

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
