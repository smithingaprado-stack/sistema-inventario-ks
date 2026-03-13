import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io

# --- 1. GESTIÓN DE BASE DE DATOS CENTRALIZADA ---
def get_connection():
    return sqlite3.connect('ks_sistema_integral_v2.db', check_same_thread=False, timeout=30)

def crear_tablas():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    c.execute('CREATE TABLE IF NOT EXISTS daños (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, motivo TEXT, foto BLOB, fecha DATETIME)')
    # Nueva tabla para nombres de tiendas
    c.execute('CREATE TABLE IF NOT EXISTS config_tiendas (id INTEGER PRIMARY KEY, nombre TEXT)')
    
    # Insertar nombres por defecto solo si la tabla está vacía
    c.execute('SELECT COUNT(*) FROM config_tiendas')
    if c.fetchone()[0] == 0:
        tiendas_iniciales = [("Tienda 1"), ("Tienda 2"), ("Tienda 3"), ("Tienda 4"), ("Tienda 5")]
        c.executemany('INSERT INTO config_tiendas (nombre) VALUES (?)', [(t,) for t in tiendas_iniciales])
    
    conn.commit()
    conn.close()

crear_tablas()

# --- 2. FUNCIONES DE CARGA DE CONFIGURACIÓN ---
def obtener_nombres_tiendas():
    conn = get_connection()
    df = pd.read_sql('SELECT nombre FROM config_tiendas', conn)
    conn.close()
    return df['nombre'].tolist()

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
st.set_page_config(page_title="KS - Sistema Integral Pro", layout="wide")

# Cargar tallas globales
TALLAS = ["S", "M", "L", "XL", "XXL"]
# Cargar nombres de tiendas dinámicos
LISTA_TIENDAS = obtener_nombres_tiendas()

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso al Sistema KS")
    pin = st.text_input("PIN de Acceso", type="password")
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
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Dashboard Almacén", "📥 Cargar Mercadería", "🚚 Enviar a Tiendas", "🚩 Reportes de Daños", "📦 Ver Pedidos", "📈 Ventas Globales", "⚙️ Configurar Tiendas"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Mis Ventas (Editar)", "⚠️ Reportar Prenda Dañada", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # --- LÓGICA ADMINISTRADOR ---
    if choice == "📊 Dashboard Almacén":
        st.header("📊 Inventario Real en Almacén Central")
        st.dataframe(obtener_resumen_almacen(), use_container_width=True)

    elif choice == "📥 Cargar Mercadería":
        st.header("📥 Ingreso de Stock")
        with st.form("form_ing", clear_on_submit=True):
            p = st.text_input("Producto").upper()
            t = st.selectbox("Talla", TALLAS)
            c = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Guardar"):
                conn = get_connection()
                conn.execute('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (?,?,?,?)', (p, t, c, datetime.now().date()))
                conn.commit(); conn.close()
                st.success("Registrado")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Enviar a Sucursales")
        df_s = obtener_resumen_almacen()
        if not df_s.empty:
            with st.form("form_env"):
                p_e = st.selectbox("Producto", df_s['producto'].unique())
                t_e = st.selectbox("Talla", TALLAS)
                d_e = st.selectbox("Tienda Destino", LISTA_TIENDAS)
                c_e = st.number_input("Cantidad", min_value=1)
                if st.form_submit_button("Confirmar Envío"):
                    conn = get_connection()
                    conn.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (?,?,?,?,?)', (p_e, t_e, c_e, d_e, datetime.now().date()))
                    conn.commit(); conn.close()
                    st.success("Enviado")
                    st.rerun()

    elif choice == "⚙️ Configurar Tiendas":
        st.header("⚙️ Personalizar Nombres de Tiendas")
        st.info("Cambia los nombres aquí y se actualizarán en todo el sistema.")
        conn = get_connection()
        tiendas_actuales = pd.read_sql('SELECT * FROM config_tiendas', conn)
        
        nuevos_nombres = []
        for i, row in tiendas_actuales.iterrows():
            nombre = st.text_input(f"Nombre Tienda {i+1}", value=row['nombre'], key=f"t_{row['id']}")
            nuevos_nombres.append((nombre, row['id']))
        
        if st.button("Actualizar Nombres"):
            c = conn.cursor()
            c.executemany('UPDATE config_tiendas SET nombre = ? WHERE id = ?', nuevos_nombres)
            conn.commit()
            conn.close()
            st.success("Nombres actualizados. Reiniciando...")
            st.rerun()

    elif choice == "🚩 Reportes de Daños":
        st.header("🚩 Prendas Dañadas")
        conn = get_connection()
        df_d = pd.read_sql('SELECT * FROM daños ORDER BY fecha DESC', conn)
        conn.close()
        for i, r in df_d.iterrows():
            with st.expander(f"{r['tienda']} - {r['producto']}"):
                st.write(f"Talla: {r['talla']} | Motivo: {r['motivo']}")
                if r['foto']: st.image(r['foto'])

    elif choice == "📦 Ver Pedidos":
        st.header("📦 Pedidos de Tiendas")
        conn = get_connection()
        df_p = pd.read_sql('SELECT * FROM pedidos ORDER BY fecha DESC', conn)
        conn.close()
        for i, r in df_p.iterrows():
            with st.expander(f"De: {r['tienda']}"):
                st.write(r['pedido_texto'])
                if st.button(f"Atendido #{r['id']}"):
                    conn = get_connection()
                    conn.execute('DELETE FROM pedidos WHERE id=?', (r['id'],))
                    conn.commit(); conn.close()
                    st.rerun()

    # --- LÓGICA TIENDA ---
    elif choice == "🛒 Registrar Venta":
        st.header("🛒 Registro de Venta")
        with st.form("f_v", clear_on_submit=True):
            t_v = st.selectbox("Tu Tienda", LISTA_TIENDAS)
            p_v = st.text_input("Producto").upper()
            ta_v = st.selectbox("Talla", TALLAS)
            ca_v = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Vender"):
                conn = get_connection()
                conn.execute('INSERT INTO ventas (tienda, producto, talla, cantidad, fecha) VALUES (?,?,?,?,?)', (t_v, p_v, ta_v, ca_v, datetime.now().date()))
                conn.commit(); conn.close()
                st.success("Venta guardada")

    elif choice == "📜 Mis Ventas (Editar)":
        st.header("📜 Historial")
        t_h = st.selectbox("Tienda", LISTA_TIENDAS)
        conn = get_connection()
        df_vh = pd.read_sql(f"SELECT * FROM ventas WHERE tienda='{t_h}' ORDER BY id DESC", conn)
        conn.close()
        for i, r in df_vh.iterrows():
            c1, c2 = st.columns([5,1])
            c1.write(f"{r['producto']} | Talla {r['talla']} | Cant: {r['cantidad']}")
            if c2.button("❌", key=f"del_{r['id']}"):
                conn = get_connection()
                conn.execute('DELETE FROM ventas WHERE id=?', (r['id'],))
                conn.commit(); conn.close()
                st.rerun()

    elif choice == "⚠️ Reportar Prenda Dañada":
        st.header("⚠️ Reportar Falla")
        with st.form("f_d"):
            ti_d = st.selectbox("Tienda", LISTA_TIENDAS)
            pr_d = st.text_input("Producto").upper()
            ta_d = st.selectbox("Talla", TALLAS)
            mo_d = st.text_area("Daño")
            fo_d = st.file_uploader("Foto", type=['jpg','png'])
            if st.form_submit_button("Enviar"):
                img = fo_d.read() if fo_d else None
                conn = get_connection()
                conn.execute('INSERT INTO daños (tienda, producto, talla, motivo, foto, fecha) VALUES (?,?,?,?,?,?)', (ti_d, pr_d, ta_d, mo_d, img, datetime.now()))
                conn.commit(); conn.close()
                st.success("Enviado")

    elif choice == "📝 Hacer Pedido":
        st.header("📝 Pedido")
        with st.form("f_p"):
            ti_p = st.selectbox("Tienda", LISTA_TIENDAS)
            li_p = st.text_area("Lista")
            if st.form_submit_button("Enviar"):
                conn = get_connection()
                conn.execute('INSERT INTO pedidos (tienda, pedido_texto, fecha) VALUES (?,?,?)', (ti_p, li_p, datetime.now()))
                conn.commit(); conn.close()
                st.success("Pedido enviado")

    if st.sidebar.button("🚪 Salir"):
        st.session_state['rol'] = None
        st.rerun()
