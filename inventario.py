import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF

# --- BASE DE DATOS ---
def get_connection():
    return sqlite3.connect('ks_pro_v9.db', check_same_thread=False)

def crear_tablas():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE, estado TEXT DEFAULT "pendiente")')
    c.execute('CREATE TABLE IF NOT EXISTS ventas_tiendas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    c.execute('CREATE TABLE IF NOT EXISTS fallas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, motivo TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS lista_tiendas (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE)')
    
    # Tiendas por defecto si está vacío
    c.execute('SELECT COUNT(*) FROM lista_tiendas')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO lista_tiendas (nombre) VALUES ("Almacen Central")')
    conn.commit()
    conn.close()

crear_tablas()

# --- INTERFAZ ---
st.set_page_config(page_title="KS - Control Total", layout="wide")
TALLAS = ["S", "M", "L", "XL"]

if 'rol' not in st.session_state: st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso KS CLOTHING")
    pin = st.text_input("PIN", type="password")
    if st.button("Ingresar"):
        if pin == "2026": st.session_state['rol'] = "admin"; st.rerun()
        elif pin == "1234": st.session_state['rol'] = "tienda"; st.rerun()
        else: st.error("PIN Incorrecto")
else:
    # Obtener tiendas actualizadas
    conn = get_connection()
    tiendas_db = pd.read_sql('SELECT nombre FROM lista_tiendas', conn)['nombre'].tolist()
    conn.close()

    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Inventario", "⚙️ Configurar Tiendas", "📥 Ingresos", "🚚 Envíos", "⚠️ Fallas", "📦 Pedidos"]
    else:
        st.sidebar.info("🏪 TIENDA")
        menu = ["🎁 Recibir", "🛒 Venta", "📜 Historial Ventas", "⚠️ Falla", "📝 Pedido"]
    
    choice = st.sidebar.selectbox("Menú:", menu)

    # --- SECCIÓN: CONFIGURAR TIENDAS (ELIMINAR Y EDITAR) ---
    if choice == "⚙️ Configurar Tiendas":
        st.header("⚙️ Gestión de Tiendas")
        
        # Añadir
        with st.expander("➕ Añadir Nueva Tienda"):
            n_t = st.text_input("Nombre de la tienda")
            if st.button("Guardar Tienda"):
                if n_t:
                    conn = get_connection()
                    try:
                        conn.execute('INSERT INTO lista_tiendas (nombre) VALUES (?)', (n_t,))
                        conn.commit()
                        st.success("Añadida!")
                        st.rerun()
                    except: st.error("Ese nombre ya existe.")
                    finally: conn.close()

        # Listado con botón de borrar funcional
        st.write("### Tiendas Activas")
        for t in tiendas_db:
            col1, col2 = st.columns([4, 1])
            col1.info(f"📍 {t}")
            # El secreto es el 'key' único para cada botón
            if col2.button("Eliminar", key=f"btn_t_{t}"):
                conn = get_connection()
                conn.execute('DELETE FROM lista_tiendas WHERE nombre=?', (t,))
                conn.commit()
                conn.close()
                st.success(f"Tienda {t} eliminada.")
                st.rerun() # Esto fuerza el refresco inmediato

    # --- SECCIÓN: HISTORIAL DE VENTAS (EDITAR/BORRAR) ---
    elif choice == "📜 Historial Ventas":
        st.header("📜 Historial de Ventas")
        t_h = st.selectbox("Tu Tienda", tiendas_db)
        conn = get_connection()
        v_df = pd.read_sql(f"SELECT * FROM ventas_tiendas WHERE tienda='{t_h}' ORDER BY id DESC", conn)
        conn.close()
        
        for i, r in v_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                c1.write(f"**{r['producto']}** | Talla: {r['talla']} | Cant: {r['cantidad']} | Fecha: {r['fecha']}")
                if c2.button("Borrar", key=f"del_v_{r['id']}"):
                    conn = get_connection()
                    conn.execute('DELETE FROM ventas_tiendas WHERE id=?', (r['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

    # --- SECCIÓN: INGRESOS (ADMIN) ---
    elif choice == "📥 Ingresos":
        st.header("📥 Registro de Ingresos")
        with st.form("in_form", clear_on_submit=True):
            p = st.text_input("Producto").upper()
            t = st.selectbox("Talla", TALLAS)
            c = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Registrar"):
                conn = get_connection()
                conn.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', (p, t, c, datetime.now().date()))
                conn.commit()
                conn.close()
                st.success("Guardado!")

    # --- BOTÓN DE CIERRE ---
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()v
