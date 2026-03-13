import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime

# --- CONFIGURACIÓN ---
# PIN Admin: 2026 | PIN Tienda: 1234
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- BASE DE DATOS ---
def get_connection():
    return sqlite3.connect('ks_database_final.db', check_same_thread=False)

def crear_tablas():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas_tiendas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
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
    if ingresos.empty: return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    df = pd.merge(ingresos, salidas, on=['producto', 'talla'], how='left').fillna(0)
    df['stock_disponible'] = df['total_in'] - df['total_out']
    return df

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema de Control KS", layout="wide")

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
    # --- MENÚS SEGÚN ROL ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 MODO ADMINISTRADOR")
        menu = ["📊 Inventario Central", "📥 Ingreso Almacén", "🚚 Enviar a Tiendas", "📈 Ventas en Tiendas", "📦 Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Historial de Ventas", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # --- LÓGICA DE TIENDA (BLOQUEADO) ---
    if choice == "🛒 Registrar Venta":
        st.header("🛒 Registrar Venta Diaria")
        with st.form("form_venta", clear_on_submit=True):
            tienda_v = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            prod_v = st.text_input("Producto vendido (Ej: HOODIE BOXY)").upper()
            talla_v = st.selectbox("Talla", TALLAS)
            cant_v = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Confirmar Venta"):
                conn = get_connection()
                conn.execute('INSERT INTO ventas_tiendas (tienda, producto, talla, cantidad, fecha) VALUES (?,?,?,?,?)',
                             (tienda_v, prod_v, talla_v, cant_v, datetime.now().date()))
                conn.commit()
                conn.close()
                st.success("✅ Venta registrada correctamente.")

    elif choice == "📜 Historial de Ventas":
        st.header("📜 Mis Ventas")
        st.info("Aquí puedes ver tus registros y borrar si cometiste un error.")
        tienda_sel = st.selectbox("Selecciona tu tienda", NOMBRES_TIENDAS)
        conn = get_connection()
        ventas_df = pd.read_sql(f"SELECT * FROM ventas_tiendas WHERE tienda='{tienda_sel}' ORDER BY id DESC", conn)
        conn.close()
        if not ventas_df.empty:
            for i, r in ventas_df.iterrows():
                col1, col2 = st.columns([5, 1])
                col1.write(f"ID: {r['id']} | {r['producto']} | Talla: {r['talla']} | Cant: {r['cantidad']} | Fecha: {r['fecha']}")
                if col2.button("❌ Borrar", key=f"del_{r['id']}"):
                    conn = get_connection()
                    conn.execute('DELETE FROM ventas_tiendas WHERE id=?', (r['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
        else:
            st.write("No hay ventas registradas hoy.")

    elif choice == "📝 Hacer Pedido":
        st.header("📝 Solicitar Mercadería")
        with st.form("form_ped", clear_on_submit=True):
            tienda_org = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            lista_txt = st.text_area("Escribe aquí lo que necesitas...")
            foto = st.file_uploader("O sube una foto de tu lista", type=['jpg','png','jpeg'])
            if st.form_submit_button("Enviar al Almacén"):
                foto_bytes = foto.read() if foto else None
                conn = get_connection()
                conn.execute('INSERT INTO pedidos (tienda, pedido_texto, foto, fecha) VALUES (?,?,?,?)',
                             (tienda_org, lista_txt, foto_bytes, datetime.now()))
                conn.commit()
                conn.close()
                st.success("🚀 Pedido enviado con éxito.")

    # --- LÓGICA DE ADMINISTRADOR ---
    elif choice == "📊 Inventario Central":
        st.header("📊 Stock Actual en Almacén")
        df_inv = obtener_stock_real()
        if not df_inv.empty:
            st.dataframe(df_inv, use_container_width=True)
        else:
            st.warning("El almacén está vacío.")

    elif choice == "📥 Ingreso Almacén":
        st.header("📥 Entrada de Mercadería")
        with st.form("form_in", clear_on_submit=True):
            p = st.text_input("Nombre del Producto").upper()
            t = st.selectbox("Talla", TALLAS)
            c_in = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Guardar en Almacén"):
                conn = get_connection()
                conn.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', 
                             (p, t, c_in, datetime.now().date()))
                conn.commit()
                conn.close()
                st.success("Ingreso registrado.")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Distribución a Sucursales")
        df_stock = obtener_stock_real()
        if not df_stock.empty:
            with st.form("form_out", clear_on_submit=True):
                p_s = st.selectbox("Producto", df_stock['producto'].unique())
                t_s = st.selectbox("Talla", df_stock[df_stock['producto']==p_s]['talla'])
                dest = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                cant = st.number_input("Cantidad a enviar", min_value=1, step=1)
                if st.form_submit_button("Confirmar Envío"):
                    conn = get_connection()
                    conn.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (?,?,?,?,?)',
                                 (p_s, t_s, cant, dest, datetime.now().date()))
                    conn.commit()
                    conn.close()
                    st.success("Envío completado.")
        else:
            st.warning("No hay stock para enviar.")

    elif choice == "📈 Ventas en Tiendas":
        st.header("📈 Reporte Global de Ventas")
        conn = get_connection()
        v_df = pd.read_sql('SELECT * FROM ventas_tiendas ORDER BY fecha DESC', conn)
        conn.close()
        st.dataframe(v_df, use_container_width=True)

    elif choice == "📦 Pedidos Recibidos":
        st.header("📦 Solicitudes Pendientes")
        conn = get_connection()
        pedidos = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn)
        conn.close()
        for i, r in pedidos.iterrows():
            with st.expander(f"De: {r['tienda']} - {r['fecha']}"):
                st.write(r['pedido_texto'])
                if r['foto']: st.image(r['foto'])
                if st.button(f"Atendido (Eliminar {r['id']})"):
                    conn = get_connection()
                    conn.execute('DELETE FROM pedidos WHERE id=?', (r['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
