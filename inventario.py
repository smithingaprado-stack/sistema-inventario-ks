import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Integral KS", layout="wide")

# --- CONEXIÓN PERMANENTE (PostgreSQL) ---
# Recuerda que esto usa los "Secrets" que configuramos antes
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    try:
        with conn.session as s:
            # Tablas base
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS pedidos (id SERIAL PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BYTEA, fecha TIMESTAMP)'))
            # Tabla de Fallados
            s.execute(text('CREATE TABLE IF NOT EXISTS fallados (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, detalle TEXT, foto BYTEA, fecha TIMESTAMP)'))
            # Tabla de Tiendas Personalizadas
            s.execute(text('CREATE TABLE IF NOT EXISTS tiendas (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE)'))
            
            # Insertar tiendas por defecto si la tabla está vacía
            res = s.execute(text('SELECT COUNT(*) FROM tiendas')).fetchone()
            if res[0] == 0:
                for t in ["Tienda Central", "Tienda Norte"]:
                    s.execute(text('INSERT INTO tiendas (nombre) VALUES (:n)'), {"n": t})
            s.commit()
    except:
        pass

inicializar_db()

# --- FUNCIONES DE APOYO ---
def get_tiendas():
    df = conn.query('SELECT nombre FROM tiendas ORDER BY nombre')
    return df['nombre'].tolist() if not df.empty else ["Tienda Central"]

TALLAS = ["S", "M", "L", "XL"]

# --- LOGIN ---
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
    tiendas_actuales = get_tiendas()
    
    # --- MENÚS ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Stock Real", "📥 Cargar Stock", "🚚 Enviar a Tiendas", "🏢 Gestionar Tiendas", "📦 Pedidos y Fallados"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Historial", "📝 Hacer Pedido", "⚠️ Reportar Fallado"]
    
    choice = st.sidebar.selectbox("Seleccione:", menu)

    # --- LÓGICA DE ADMIN ---
    if choice == "🏢 Gestionar Tiendas":
        st.header("🏢 Configuración de Tiendas")
        col1, col2 = st.columns(2)
        with col1:
            nueva_t = st.text_input("Nombre de nueva tienda")
            if st.button("Añadir Tienda"):
                with conn.session as s:
                    s.execute(text('INSERT INTO tiendas (nombre) VALUES (:n)'), {"n": nueva_t})
                    s.commit()
                st.rerun()
        with col2:
            t_borrar = st.selectbox("Eliminar tienda", tiendas_actuales)
            if st.button("Eliminar"):
                with conn.session as s:
                    s.execute(text('DELETE FROM tiendas WHERE nombre = :n'), {"n": t_borrar})
                    s.commit()
                st.rerun()

    elif choice == "📊 Stock Real":
        st.header("📊 Inventario en Almacén")
        df_in = conn.query('SELECT producto, talla, SUM(cantidad) as t_in FROM ingresos GROUP BY producto, talla')
        df_out = conn.query('SELECT producto, talla, SUM(cantidad) as t_out FROM distribucion GROUP BY producto, talla')
        if df_in.empty: st.info("Almacén vacío")
        else:
            df = pd.merge(df_in, df_out, on=['producto', 'talla'], how='left').fillna(0)
            df['Disponible'] = df['t_in'] - df['t_out']
            st.dataframe(df[df['Disponible'] > 0], use_container_width=True)

    elif choice == "📦 Pedidos y Fallados":
        tab1, tab2 = st.tabs(["📦 Pedidos de Mercadería", "⚠️ Reportes de Fallados"])
        with tab1:
            peds = conn.query('SELECT * FROM pedidos ORDER BY fecha DESC')
            st.write(peds)
        with tab2:
            fallas = conn.query('SELECT * FROM fallados ORDER BY fecha DESC')
            for i, r in fallas.iterrows():
                with st.expander(f"Falla en {r['tienda']} - {r['producto']}"):
                    st.write(f"Detalle: {r['detalle']}")
                    if r['foto']: st.image(r['foto'])

    # --- LÓGICA DE TIENDA ---
    elif choice == "⚠️ Reportar Fallado":
        st.header("⚠️ Reportar Prenda con Falla")
        with st.form("form_falla", clear_on_submit=True):
            t_f = st.selectbox("Tu Tienda", tiendas_actuales)
            p_f = st.text_input("Producto fallado")
            d_f = st.text_area("Explica el defecto (ej. hueco en manga, mancha)")
            f_f = st.file_uploader("Foto de la falla", type=['jpg', 'png'])
            if st.form_submit_button("Enviar Reporte"):
                img_data = f_f.read() if f_f else None
                with conn.session as s:
                    s.execute(text('INSERT INTO fallados (tienda, producto, detalle, foto, fecha) VALUES (:t, :p, :d, :f, :fe)'),
                              {"t":t_f, "p":p_f, "d":d_f, "f":img_data, "fe":datetime.now()})
                    s.commit()
                st.success("Reporte enviado al administrador")

    elif choice == "🛒 Registrar Venta":
        with st.form("v", clear_on_submit=True):
            ti = st.selectbox("Tienda", tiendas_actuales)
            pr = st.text_input("Producto").upper()
            ta = st.selectbox("Talla", TALLAS)
            ca = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar Venta"):
                with conn.session as s:
                    s.execute(text('INSERT INTO ventas (tienda, producto, talla, cantidad, fecha) VALUES (:ti, :p, :ta, :c, :f)'),
                              {"ti":ti, "p":pr, "ta":ta, "c":ca, "f":datetime.now().date()})
                    s.commit()
                st.success("Venta guardada")

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
