import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

st.set_page_config(page_title="Sistema Integral KS", layout="wide", page_icon="📦")

# Conexión profesional que NO borra datos
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    try:
        with conn.session as s:
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS pedidos (id SERIAL PRIMARY KEY, tienda TEXT, pedido TEXT, fecha TIMESTAMP)'))
            s.commit()
    except:
        pass

inicializar_db()

# --- 2. FUNCIONES DE CÁLCULO ---
def obtener_stock_real():
    df_in = conn.query('SELECT producto, talla, SUM(cantidad) as t_in FROM ingresos GROUP BY producto, talla')
    df_out = conn.query('SELECT producto, talla, SUM(cantidad) as t_out FROM distribucion GROUP BY producto, talla')
    if df_in.empty: return pd.DataFrame(columns=['producto', 'talla', 'Disponible'])
    df = pd.merge(df_in, df_out, on=['producto', 'talla'], how='left').fillna(0)
    df['Disponible'] = df['t_in'] - df['t_out']
    return df[df['Disponible'] > 0]

# --- 3. SEGURIDAD Y LOGIN ---
if 'rol' not in st.session_state: st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso Sistema KS")
    col1, _ = st.columns([1, 2])
    pin = col1.text_input("Introduce tu PIN", type="password")
    if col1.button("Ingresar"):
        if pin == "2026": st.session_state['rol'] = "admin"; st.rerun()
        elif pin == "1234": st.session_state['rol'] = "tienda"; st.rerun()
        else: st.error("PIN Incorrecto")
else:
    # --- 4. MENÚS SEGÚN ROL ---
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 MODO ADMINISTRADOR")
        menu = ["📊 Inventario Central", "📥 Ingreso Almacén", "🚚 Enviar a Tiendas", "📈 Reporte de Ventas", "📦 Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Historial y Editar", "📝 Solicitar Mercadería"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # --- 5. LÓGICA DE ADMINISTRADOR ---
    if choice == "📊 Inventario Central":
        st.header("📊 Stock Real en Almacén")
        df_stock = obtener_stock_real()
        st.dataframe(df_stock, use_container_width=True)
        st.info("Este stock disminuye automáticamente cuando envías mercadería a las tiendas.")

    elif choice == "📥 Ingreso Almacén":
        st.header("📥 Entrada de Mercadería (Producción)")
        with st.form("f_in", clear_on_submit=True):
            p = st.text_input("Nombre del Producto (ej: HOODIE GOTHIC)").upper()
            t = st.selectbox("Talla", TALLAS)
            c = st.number_input("Cantidad Producida", min_value=1, step=1)
            if st.form_submit_button("Guardar en Almacén"):
                with conn.session as s:
                    s.execute(text('INSERT INTO ingresos (producto, talla, cantidad, fecha) VALUES (:p, :t, :c, :f)'),
                              {"p":p, "t":t, "c":c, "f":datetime.now().date()})
                    s.commit()
                st.success(f"✅ {c} unidades de {p} añadidas al inventario central.")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Distribución a Sucursales")
        df_s = obtener_stock_real()
        if not df_s.empty:
            with st.form("f_env", clear_on_submit=True):
                p_env = st.selectbox("Producto", df_s['producto'].unique())
                t_env = st.selectbox("Talla", TALLAS)
                dest = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                c_env = st.number_input("Cantidad a enviar", min_value=1)
                if st.form_submit_button("Confirmar Envío"):
                    with conn.session as s:
                        s.execute(text('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (:p, :ta, :c, :ti, :f)'),
                                  {"p":p_env, "ta":t_env, "c":c_env, "ti":dest, "f":datetime.now().date()})
                        s.commit()
                    st.success("🚚 Mercadería enviada y descontada de almacén central.")
                    st.rerun()

    elif choice == "📈 Reporte de Ventas":
        st.header("📈 Ventas Globales de Todas las Tiendas")
        df_ventas = conn.query("SELECT * FROM ventas ORDER BY fecha DESC")
        if not df_ventas.empty:
            st.dataframe(df_ventas, use_container_width=True)
            total = df_ventas['cantidad'].sum()
            st.metric("Total Prendas Vendidas", f"{total} uds")
        else: st.warning("Aún no se han registrado ventas.")

    elif choice == "📦 Pedidos Recibidos":
        st.header("📦 Pedidos Pendientes de Tiendas")
        df_p = conn.query("SELECT * FROM pedidos ORDER BY fecha DESC")
        st.dataframe(df_p, use_container_width=True)

    # --- 6. LÓGICA DE TIENDA ---
    elif choice == "🛒 Registrar Venta":
        st.header("🛒 Registrar Venta Diaria")
        with st.form("f_v", clear_on_submit=True):
            ti = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            pr = st.text_input("Producto vendido").upper()
            ta = st.selectbox("Talla", TALLAS)
            ca = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Finalizar Venta"):
                with conn.session as s:
                    s.execute(text('INSERT INTO ventas (tienda, producto, talla, cantidad, fecha) VALUES (:ti, :p, :ta, :ca, :f)'),
                              {"ti":ti, "p":pr, "ta":ta, "ca":ca, "f":datetime.now().date()})
                    s.commit()
                st.success("✅ Venta registrada correctamente.")

    elif choice == "📜 Historial y Editar":
        st.header("📜 Mis Ventas")
        t_sel = st.selectbox("Selecciona tu tienda para ver/editar:", NOMBRES_TIENDAS)
        df_v = conn.query(f"SELECT * FROM ventas WHERE tienda='{t_sel}' ORDER BY id DESC")
        for i, r in df_v.iterrows():
            col1, col2 = st.columns([4, 1])
            col1.write(f"📅 {r['fecha']} | {r['producto']} | Talla: {r['talla']} | Cant: {r['cantidad']}")
            if col2.button("Eliminar", key=f"del_{r['id']}"):
                with conn.session as s:
                    s.execute(text(f"DELETE FROM ventas WHERE id={r['id']}")); s.commit()
                st.rerun()

    elif choice == "📝 Solicitar Mercadería":
        st.header("📝 Nota de Pedido al Almacén")
        with st.form("f_p", clear_on_submit=True):
            t_ped = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            msg = st.text_area("Escribe los productos y tallas que te faltan...")
            if st.form_submit_button("Enviar Pedido"):
                with conn.session as s:
                    s.execute(text('INSERT INTO pedidos (tienda, pedido, fecha) VALUES (:t, :p, :f)'),
                              {"t":t_ped, "p":msg, "f":datetime.now()})
                    s.commit()
                st.success("🚀 Pedido enviado al administrador.")

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
