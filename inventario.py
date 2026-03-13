import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime

# --- CONFIGURACIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- BASE DE DATOS ---
def get_connection():
    return sqlite3.connect('ks_sistema_pro_v6.db', check_same_thread=False)

def crear_tablas():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE, estado TEXT DEFAULT "pendiente")')
    c.execute('CREATE TABLE IF NOT EXISTS ventas_tiendas (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    # Nueva tabla para fallas
    c.execute('CREATE TABLE IF NOT EXISTS fallas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, motivo TEXT, fecha DATE)')
    conn.commit()
    conn.close()

crear_tablas()

# --- FUNCIONES ---
def obtener_stock_central():
    conn = get_connection()
    ingresos = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla', conn)
    salidas = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_out FROM distribucion GROUP BY producto, talla', conn)
    # Sumamos las fallas que regresan al almacén central (si decides reingresarlas como merma)
    fallas = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_fallas FROM fallas GROUP BY producto, talla', conn)
    conn.close()
    
    if ingresos.empty: return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    df = pd.merge(ingresos, salidas, on=['producto', 'talla'], how='left').fillna(0)
    df = pd.merge(df, fallas, on=['producto', 'talla'], how='left').fillna(0)
    
    # El stock disponible es lo que entró, menos lo que envié a tiendas.
    df['stock_disponible'] = df['total_in'] - df['total_out']
    return df

# --- INTERFAZ ---
st.set_page_config(page_title="KS - Control Total & Fallas", layout="wide")

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso Sistema KS")
    pin = st.text_input("PIN", type="password")
    if st.button("Ingresar"):
        if pin == "2026": st.session_state['rol'] = "admin"; st.rerun()
        elif pin == "1234": st.session_state['rol'] = "tienda"; st.rerun()
        else: st.error("PIN Incorrecto")
else:
    # --- MENÚS ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Stock Central", "📥 Ingresar Mercadería", "🚚 Enviar a Tiendas", "⚠️ Ver Prendas Falladas", "📦 Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 TIENDA")
        menu = ["🎁 Confirmar Recepción", "🛒 Registrar Venta", "⚠️ Reportar Falla", "📜 Historial Ventas", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Ir a:", menu)

    # --- MÓDULO DE FALLAS (TIENDA) ---
    if choice == "⚠️ Reportar Falla":
        st.header("⚠️ Reportar Prenda Fallada")
        st.write("Usa esta opción si una prenda llegó mal de fábrica y debe volver al almacén.")
        with st.form("form_falla"):
            t_f = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            p_f = st.text_input("Producto Fallado").upper()
            ta_f = st.selectbox("Talla", TALLAS)
            c_f = st.number_input("Cantidad", min_value=1)
            motivo = st.text_area("Explica la falla (ej: cierre roto, mancha, tela picada)")
            if st.form_submit_button("Enviar a Almacén Central"):
                conn = get_connection()
                conn.execute('INSERT INTO fallas (tienda, producto, talla, cantidad, motivo, fecha) VALUES (?,?,?,?,?,?)',
                             (t_f, p_f, ta_f, c_f, motivo, datetime.now().date()))
                conn.commit()
                conn.close()
                st.success("⚠️ Reporte enviado. Por favor, entrega la prenda físicamente al almacén.")

    # --- VER FALLAS (ADMIN) ---
    elif choice == "⚠️ Ver Prendas Falladas":
        st.header("⚠️ Reportes de Fallas desde Tiendas")
        conn = get_connection()
        df_fallas = pd.read_sql('SELECT * FROM fallas ORDER BY fecha DESC', conn)
        conn.close()
        if not df_fallas.empty:
            st.dataframe(df_fallas, use_container_width=True)
            if st.button("Limpiar historial de fallas procesadas"):
                conn = get_connection(); conn.execute('DELETE FROM fallas'); conn.commit(); conn.close(); st.rerun()
        else:
            st.info("No hay reportes de fallas pendientes.")

    # --- RESTO DE LÓGICA (ADMIN & TIENDA) ---
    elif choice == "🎁 Confirmar Recepción":
        st.header("🎁 Confirmar Llegada de Mercadería")
        t_nombre = st.selectbox("Selecciona tu tienda", NOMBRES_TIENDAS)
        conn = get_connection(); pendientes = pd.read_sql(f"SELECT * FROM distribucion WHERE tienda='{t_nombre}' AND estado='pendiente'", conn); conn.close()
        if not pendientes.empty:
            for i, r in pendientes.iterrows():
                with st.container(border=True):
                    st.write(f"**Envío #{r['id']}**: {r['producto']} | Talla: {r['talla']} | Cant: {r['cantidad']}")
                    if st.button("✅ Confirmar Recepción", key=f"c_{r['id']}"):
                        conn = get_connection(); conn.execute("UPDATE distribucion SET estado='recibido' WHERE id=?", (r['id'],)); conn.commit(); conn.close(); st.rerun()
        else: st.info("Sin envíos pendientes.")

    elif choice == "📊 Stock Central":
        st.header("📊 Inventario en Almacén")
        st.dataframe(obtener_stock_central(), use_container_width=True)

    elif choice == "📥 Ingresar Mercadería":
        st.header("📥 Ingreso")
        with st.form("in"):
            p = st.text_input("Producto").upper(); t = st.selectbox("Talla", TALLAS); c = st.number_input("Cant", min_value=1)
            if st.form_submit_button("Guardar"):
                conn = get_connection(); conn.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', (p, t, c, datetime.now().date())); conn.commit(); conn.close(); st.success("Ok")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Distribución")
        df_s = obtener_stock_central()
        if not df_s.empty:
            with st.form("out"):
                p_s = st.selectbox("Producto", df_s['producto'].unique()); t_s = st.selectbox("Talla", TALLAS); d = st.selectbox("Destino", NOMBRES_TIENDAS); cn = st.number_input("Cant", min_value=1)
                if st.form_submit_button("Enviar"):
                    conn = get_connection(); conn.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha, estado) VALUES (?,?,?,?,?,?)', (p_s, t_s, cn, d, datetime.now().date(), "pendiente")); conn.commit(); conn.close(); st.success("En camino...")

    elif choice == "🛒 Registrar Venta":
        st.header("🛒 Registrar Venta")
        with st.form("v"):
            t_v = st.selectbox("Tienda", NOMBRES_TIENDAS); p_v = st.text_input("Producto").upper(); ta_v = st.selectbox("Talla", TALLAS); c_v = st.number_input("Cant", min_value=1)
            if st.form_submit_button("Guardar"):
                conn = get_connection(); conn.execute('INSERT INTO ventas_tiendas (tienda, producto, talla, cantidad, fecha) VALUES (?,?,?,?,?)', (t_v, p_v, ta_v, c_v, datetime.now().date())); conn.commit(); conn.close(); st.success("Venta guardada")

    elif choice == "📜 Historial Ventas":
        st.header("📜 Historial")
        t_h = st.selectbox("Tienda", NOMBRES_TIENDAS)
        conn = get_connection(); v_df = pd.read_sql(f"SELECT * FROM ventas_tiendas WHERE tienda='{t_h}' ORDER BY id DESC", conn); conn.close()
        for i, r in v_df.iterrows():
            st.write(f"{r['producto']} - Talla: {r['talla']} - Cant: {r['cantidad']} ", st.button("❌", key=f"v_{r['id']}"))

    elif choice == "📝 Hacer Pedido":
        st.header("📝 Nuevo Pedido")
        with st.form("ped"):
            t_p = st.selectbox("Tienda", NOMBRES_TIENDAS); txt = st.text_area("Lista..."); f = st.file_uploader("Foto", type=['jpg','png'])
            if st.form_submit_button("Enviar"):
                fb = f.read() if f else None
                conn = get_connection(); conn.execute('INSERT INTO pedidos (tienda, pedido_texto, foto, fecha) VALUES (?,?,?,?)', (t_p, txt, fb, datetime.now())); conn.commit(); conn.close(); st.success("Enviado")

    elif choice == "📦 Pedidos Recibidos":
        st.header("📦 Pedidos Pendientes")
        conn = get_connection(); ped = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn); conn.close()
        for i, r in ped.iterrows():
            with st.expander(f"{r['tienda']} - {r['fecha']}"):
                st.write(r['pedido_texto'])
                if r['foto']: st.image(r['foto'])
                if st.button("Atendido", key=f"at_{r['id']}"):
                    conn = get_connection(); conn.execute('DELETE FROM pedidos WHERE id=?', (r['id'],)); conn.commit(); conn.close(); st.rerun()

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None; st.rerun()
