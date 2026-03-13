import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# --- CONFIGURACIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- CONEXIÓN PERMANENTE ---
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    try:
        with conn.session as s:
            # Creamos todas las tablas necesarias
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS pedidos (id SERIAL PRIMARY KEY, tienda TEXT, pedido TEXT, fecha TIMESTAMP)'))
            s.commit()
    except Exception as e:
        st.error(f"Error de conexión: {e}")

inicializar_db()

# --- FUNCIONES DE CÁLCULO ---
def obtener_stock():
    df_in = conn.query('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla')
    df_out = conn.query('SELECT producto, talla, SUM(cantidad) as total_out FROM distribucion GROUP BY producto, talla')
    if df_in.empty: return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    df = pd.merge(df_in, df_out, on=['producto', 'talla'], how='left').fillna(0)
    df['stock_disponible'] = df['total_in'] - df['total_out']
    return df[df['stock_disponible'] > 0]

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema Integral KS", layout="wide")

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso Sistema KS")
    pin = st.text_input("Introduce tu PIN", type="password")
    if st.button("Ingresar"):
        if pin == "2026": st.session_state['rol'] = "admin"; st.rerun()
        elif pin == "1234": st.session_state['rol'] = "tienda"; st.rerun()
        else: st.error("PIN Incorrecto")
else:
    # --- MENÚS ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Inventario Central", "📥 Ingreso Almacén", "🚚 Enviar a Tiendas", "📈 Reporte de Ventas", "📦 Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Historial y Borrar", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # --- LÓGICA ADMINISTRADOR ---
    if choice == "📊 Inventario Central":
        st.header("📊 Stock Disponible en Almacén")
        st.dataframe(obtener_stock(), use_container_width=True)

    elif choice == "📥 Ingreso Almacén":
        st.header("📥 Cargar Mercadería")
        with st.form("in", clear_on_submit=True):
            p = st.text_input("Producto").upper(); t = st.selectbox("Talla", TALLAS); c = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar Stock"):
                with conn.session as s:
                    s.execute(text('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (:p, :t, :c, :f)'),
                              {"p":p, "t":t, "c":c, "f":datetime.now().date()})
                    s.commit()
                st.success("📦 Cargado con éxito")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Distribución a Sucursales")
        df_s = obtener_stock()
        if not df_s.empty:
            with st.form("env", clear_on_submit=True):
                p_s = st.selectbox("Producto", df_s['producto'].unique()); ta_s = st.selectbox("Talla", TALLAS)
                ti = st.selectbox("Destino", NOMBRES_TIENDAS); c_e = st.number_input("Cantidad", min_value=1)
                if st.form_submit_button("Confirmar Envío"):
                    with conn.session as s:
                        s.execute(text('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (:p, :ta, :c, :ti, :f)'),
                                  {"p":p_s, "ta":ta_s, "c":c_e, "ti":ti, "f":datetime.now().date()})
                        s.commit()
                    st.success("🚚 Mercadería enviada"); st.rerun()

    elif choice == "📈 Reporte de Ventas":
        st.header("📈 Ventas de todas las tiendas")
        df_v = conn.query('SELECT * FROM ventas ORDER BY fecha DESC')
        st.dataframe(df_v, use_container_width=True)

    elif choice == "📦 Pedidos Recibidos":
        st.header("📦 Solicitudes Pendientes")
        pedidos = conn.query('SELECT * FROM pedidos ORDER BY fecha DESC')
        for i, r in pedidos.iterrows():
            with st.expander(f"De: {r['tienda']} - {r['fecha']}"):
                st.write(r['pedido'])
                if st.button(f"Atendido (ID {r['id']})"):
                    with conn.session as s:
                        s.execute(text(f"DELETE FROM pedidos WHERE id={r['id']}")); s.commit()
                    st.rerun()

    # --- LÓGICA TIENDA ---
    elif choice == "🛒 Registrar Venta":
        st.header("🛒 Registro de Venta Diaria")
        with st.form("v", clear_on_submit=True):
            ti = st.selectbox("Tu Tienda", NOMBRES_TIENDAS); p = st.text_input("Producto").upper()
            ta = st.selectbox("Talla", TALLAS); c = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar Venta"):
                with conn.session as s:
                    s.execute(text('INSERT INTO ventas (tienda, producto, talla, cantidad, fecha) VALUES (:ti, :p, :ta, :c, :f)'),
                              {"ti":ti, "p":p, "ta":ta, "c":c, "f":datetime.now().date()})
                    s.commit()
                st.success("✅ Venta guardada")

    elif choice == "📜 Historial y Borrar":
        st.header("📜 Mis Ventas (Borrar para corregir)")
        tienda = st.selectbox("Selecciona tu tienda", NOMBRES_TIENDAS)
        df_v = conn.query(f"SELECT * FROM ventas WHERE tienda='{tienda}' ORDER BY id DESC")
        for i, r in df_v.iterrows():
            col1, col2 = st.columns([4,1])
            col1.write(f"{r['producto']} | Talla {r['talla']} | Cant: {r['cantidad']} | Fecha: {r['fecha']}")
            if col2.button("❌", key=f"del_{r['id']}"):
                with conn.session as s:
                    s.execute(text(f"DELETE FROM ventas WHERE id={r['id']}")); s.commit()
                st.rerun()

    elif choice == "📝 Hacer Pedido":
        st.header("📝 Solicitar Mercadería")
        with st.form("p", clear_on_submit=True):
            ti = st.selectbox("Tu Tienda", NOMBRES_TIENDAS); txt = st.text_area("Escribe tu pedido...")
            if st.form_submit_button("Enviar Pedido"):
                with conn.session as s:
                    s.execute(text('INSERT INTO pedidos (tienda, pedido, fecha) VALUES (:ti, :txt, :f)'),
                              {"ti":ti, "txt":txt, "f":datetime.now()})
                    s.commit()
                st.success("🚀 Pedido enviado")

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
