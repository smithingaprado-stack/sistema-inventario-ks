import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN PERSONALIZABLE ---
# Puedes cambiar estos nombres por los de tus sucursales reales
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL", "XXL"]

# --- 2. BASE DE DATOS CENTRALIZADA ---
def get_connection():
    # Esta base de datos une el Almacén con todas las Tiendas
    return sqlite3.connect('ks_sistema_integral.db', check_same_thread=False, timeout=30)

def crear_tablas():
    conn = get_connection()
    c = conn.cursor()
    # Entradas de stock al almacén central
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    # Salidas de stock del almacén hacia las tiendas
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    # Ventas diarias de cada tienda
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    # Pedidos de mercadería de tiendas al almacén
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    # Reportes de prendas con fallas o dañadas
    c.execute('CREATE TABLE IF NOT EXISTS daños (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, motivo TEXT, foto BLOB, fecha DATETIME)')
    conn.commit()
    conn.close()

crear_tablas()

# --- 3. LÓGICA DE INVENTARIO VINCULADO ---
def obtener_resumen_almacen():
    conn = get_connection()
    ing = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla', conn)
    out = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_out FROM distribucion GROUP BY producto, talla', conn)
    conn.close()
    if ing.empty: return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    df = pd.merge(ing, out, on=['producto', 'talla'], how='left').fillna(0)
    df['stock_disponible'] = df['total_in'] - df['total_out']
    return df

# --- 4. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="KS - Sistema Integral de Control", layout="wide")

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

# --- PANTALLA DE LOGIN ---
if st.session_state['rol'] is None:
    st.title("🔐 Acceso al Sistema KS")
    st.subheader("Control de Almacén y Gestión de Tiendas")
    pin = st.text_input("PIN de Acceso", type="password", help="Introduce 2026 para Admin o 1234 para Tienda")
    if st.button("Ingresar"):
        if pin == "2026":
            st.session_state['rol'] = "admin"
            st.rerun()
        elif pin == "1234":
            st.session_state['rol'] = "tienda"
            st.rerun()
        else:
            st.error("PIN incorrecto.")

else:
    # --- MENÚS SEGÚN ROL ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Dashboard Almacén", "📥 Cargar Mercadería", "🚚 Enviar a Tiendas", "🚩 Reportes de Daños", "📦 Ver Pedidos de Tiendas", "📈 Historial de Ventas Global"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Mis Ventas (Editar)", "⚠️ Reportar Prenda Dañada", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # --- LÓGICA ADMINISTRADOR ---
    if choice == "📊 Dashboard Almacén":
        st.header("📊 Inventario Real en Almacén Central")
        df_stock = obtener_resumen_almacen()
        if not df_stock.empty:
            st.dataframe(df_stock, use_container_width=True)
        else:
            st.info("No hay datos de stock registrados aún.")

    elif choice == "📥 Cargar Mercadería":
        st.header("📥 Ingreso de Nuevas Prendas")
        with st.form("form_ingreso", clear_on_submit=True):
            p_nom = st.text_input("Nombre del Producto").upper()
            p_tal = st.selectbox("Talla", TALLAS)
            p_can = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Guardar en Stock Central"):
                conn = get_connection()
                conn.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', 
                             (p_nom, p_tal, p_can, datetime.now().date()))
                conn.commit(); conn.close()
                st.success(f"Registrado: {p_nom} - {p_tal}")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Distribución a Sucursales")
        df_stock = obtener_resumen_almacen()
        if not df_stock.empty:
            with st.form("form_envio", clear_on_submit=True):
                p_env = st.selectbox("Seleccione Producto", df_stock['producto'].unique())
                t_env = st.selectbox("Seleccione Talla", TALLAS)
                t_des = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                c_env = st.number_input("Cantidad a enviar", min_value=1, step=1)
                if st.form_submit_button("Confirmar Envío"):
                    conn = get_connection()
                    conn.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (?,?,?,?,?)',
                                 (p_env, t_env, c_env, t_des, datetime.now().date()))
                    conn.commit(); conn.close()
                    st.success("Mercadería enviada y descontada del almacén.")
                    st.rerun()
        else:
            st.warning("Almacén vacío.")

    elif choice == "🚩 Reportes de Daños":
        st.header("🚩 Prendas Reportadas con Fallas")
        conn = get_connection()
        df_d = pd.read_sql('SELECT * FROM daños ORDER BY fecha DESC', conn)
        conn.close()
        for i, r in df_d.iterrows():
            with st.expander(f"Reporte de {r['tienda']} - {r['producto']} ({r['fecha']})"):
                st.write(f"**Talla:** {r['talla']} | **Falla:** {r['motivo']}")
                if r['foto']: st.image(r['foto'])

    elif choice == "📦 Ver Pedidos de Tiendas":
        st.header("📦 Solicitudes de Mercadería")
        conn = get_connection()
        df_p = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn)
        conn.close()
        for i, r in df_p.iterrows():
            with st.expander(f"Pedido de {r['tienda']} - {r['fecha']}"):
                st.write(r['pedido_texto'])
                if r['foto']: st.image(r['foto'])
                if st.button(f"Marcar como Atendido #{r['id']}"):
                    conn = get_connection()
                    conn.execute('DELETE FROM pedidos WHERE id=?', (r['id'],))
                    conn.commit(); conn.close()
                    st.rerun()

    # --- LÓGICA TIENDA ---
    elif choice == "🛒 Registrar Venta":
        st.header("🛒 Registro de Venta")
        with st.form("form_v", clear_on_submit=True):
            tienda_v = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            prod_v = st.text_input("Producto vendido").upper()
            talla_v = st.selectbox("Talla", TALLAS)
            cant_v = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Confirmar Venta"):
                conn = get_connection()
                conn.execute('INSERT INTO ventas (tienda, producto, talla, cantidad, fecha) VALUES (?,?,?,?,?)',
                             (tienda_v, prod_v, talla_v, cant_v, datetime.now().date()))
                conn.commit(); conn.close()
                st.success("Venta guardada.")

    elif choice == "📜 Mis Ventas (Editar)":
        st.header("📜 Historial y Edición de Ventas")
        tienda_h = st.selectbox("Seleccione tienda para ver registros", NOMBRES_TIENDAS)
        conn = get_connection()
        df_vh = pd.read_sql(f"SELECT * FROM ventas WHERE tienda='{tienda_h}' ORDER BY id DESC", conn)
        conn.close()
        for i, r in df_vh.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.write(f"{r['producto']} | Talla {r['talla']} | Cant: {r['cantidad']} | {r['fecha']}")
            if c2.button("❌ Borrar", key=f"del_v_{r['id']}"):
                conn = get_connection()
                conn.execute('DELETE FROM ventas WHERE id=?', (r['id'],))
                conn.commit(); conn.close()
                st.rerun()

    elif choice == "⚠️ Reportar Prenda Dañada":
        st.header("⚠️ Reporte de Prenda con Falla")
        with st.form("form_daño", clear_on_submit=True):
            t_daño = st.selectbox("Tienda que reporta", NOMBRES_TIENDAS)
            p_daño = st.text_input("Producto con falla").upper()
            ta_daño = st.selectbox("Talla", TALLAS)
            desc_daño = st.text_area("Describa el problema")
            foto_daño = st.file_uploader("Subir foto de la prenda", type=['jpg','png'])
            if st.form_submit_button("Enviar Reporte"):
                f_bytes = foto_daño.read() if foto_daño else None
                conn = get_connection()
                conn.execute('INSERT INTO daños (tienda, producto, talla, motivo, foto, fecha) VALUES (?,?,?,?,?,?)',
                             (t_daño, p_daño, ta_daño, desc_daño, f_bytes, datetime.now()))
                conn.commit(); conn.close()
                st.success("Reporte enviado al Almacén Central.")

    elif choice == "📝 Hacer Pedido":
        st.header("📝 Solicitar Mercadería")
        with st.form("form_pedido", clear_on_submit=True):
            t_ped = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            listado = st.text_area("Escribe aquí lo que te hace falta...")
            foto_ped = st.file_uploader("O sube foto de tu lista", type=['jpg','png'])
            if st.form_submit_button("Enviar Pedido"):
                fp_bytes = foto_ped.read() if foto_ped else None
                conn = get_connection()
                conn.execute('INSERT INTO pedidos (tienda, pedido_texto, foto, fecha) VALUES (?,?,?,?)',
                             (t_ped, listado, fp_bytes, datetime.now()))
                conn.commit(); conn.close()
                st.success("Pedido enviado.")

    # --- BOTÓN DE CIERRE ---
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
