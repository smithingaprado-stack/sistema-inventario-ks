import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import plotly.express as px

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="KS CLOTHING - SISTEMA INTEGRAL", layout="wide")

# --- CONEXIÓN ---
conn = st.connection("postgresql", type="sql")

# --- INICIALIZACIÓN DE TABLAS AVANZADAS ---
def init_db():
    with conn.session as s:
        # Tabla de tiendas personalizable
        s.execute(text('CREATE TABLE IF NOT EXISTS config_tiendas (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE)'))
        # Tablas de inventario
        s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
        s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
        s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, precio FLOAT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
        # Tabla de fallados
        s.execute(text('CREATE TABLE IF NOT EXISTS fallados (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, motivo TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
        
        # Insertar tiendas por defecto si la tabla está vacía
        res = s.execute(text("SELECT COUNT(*) FROM config_tiendas")).fetchone()
        if res[0] == 0:
            for t in ["Tienda Central", "Tienda Norte", "Tienda Sur"]:
                s.execute(text("INSERT INTO config_tiendas (nombre) VALUES (:n)"), {"n": t})
        s.commit()

init_db()

# --- FUNCIONES DE SOPORTE ---
def query_db(query, params=None):
    try:
        if params:
            return conn.query(query, params=params, ttl=0)
        return conn.query(query, ttl=0)
    except:
        return pd.DataFrame()

def get_tiendas():
    df = query_db("SELECT nombre FROM config_tiendas ORDER BY id")
    return df['nombre'].tolist() if not df.empty else ["Tienda por Defecto"]

# --- LOGIN ---
if 'auth' not in st.session_state:
    st.session_state.auth = False
    st.session_state.rol = None

if not st.session_state.auth:
    st.title("🛡️ KS CLOTHING - Acceso")
    pin = st.text_input("PIN de Seguridad", type="password")
    if st.button("Ingresar"):
        if pin == "2026":
            st.session_state.auth, st.session_state.rol = True, "Admin"
            st.rerun()
        elif pin == "1234":
            st.session_state.auth, st.session_state.rol = True, "Tienda"
            st.rerun()
        else: st.error("PIN Incorrecto")
else:
    tiendas_lista = get_tiendas()
    st.sidebar.title(f"KS - {st.session_state.rol}")
    
    if st.session_state.rol == "Admin":
        menu = ["📊 Dashboard", "📥 Almacén Central", "🚚 Distribución", "⚠️ Gestión Fallados", "📜 Historial Ventas", "⚙️ Configuración"]
    else:
        menu = ["💰 Registrar Venta", "🚨 Reportar Fallado", "📦 Mi Stock"]

    choice = st.sidebar.radio("Menú", menu)
    if st.sidebar.button("Salir"):
        st.session_state.auth = False
        st.rerun()

    # --- PÁGINAS ADMINISTRADOR ---
    if choice == "📊 Dashboard":
        st.header("📊 Resumen General KS")
        df_v = query_db("SELECT * FROM ventas")
        if not df_v.empty:
            st.metric("Ventas Totales", f"S/. {df_v['precio'].sum():.2f}")
            fig = px.bar(df_v, x='tienda', y='precio', color='producto', title="Ventas por Tienda")
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Esperando datos de ventas...")

    elif choice == "📥 Almacén Central":
        st.header("📥 Ingreso de Mercadería")
        with st.form("ing_form"):
            prod = st.text_input("Producto").upper()
            talla = st.selectbox("Talla", ["S", "M", "L", "XL", "XXL"])
            cant = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar Ingreso"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ingresos (producto, talla, cantidad) VALUES (:p, :t, :c)"),
                              {"p":prod, "t":talla, "c":cant})
                    s.commit()
                st.success("Cargado al almacén central")

    elif choice == "⚙️ Configuración":
        st.header("⚙️ Configuración de Tiendas")
        st.subheader("Editar Nombres de Tiendas")
        
        tiendas_actuales = query_db("SELECT id, nombre FROM config_tiendas")
        for idx, row in tiendas_actuales.iterrows():
            col1, col2 = st.columns([3, 1])
            nuevo_nombre = col1.text_input(f"Tienda {row['id']}", value=row['nombre'], key=f"t_{row['id']}")
            if col2.button("Actualizar", key=f"b_{row['id']}"):
                with conn.session as s:
                    s.execute(text("UPDATE config_tiendas SET nombre = :n WHERE id = :id"), {"n":nuevo_nombre, "id":row['id']})
                    s.commit()
                st.rerun()
        
        if st.button("➕ Agregar Nueva Tienda"):
            with conn.session as s:
                s.execute(text("INSERT INTO config_tiendas (nombre) VALUES ('Nueva Tienda')"))
                s.commit()
            st.rerun()

    elif choice == "⚠️ Gestión Fallados":
        st.header("⚠️ Reportes de Prendas Falladas")
        df_fal = query_db("SELECT * FROM fallados")
        st.dataframe(df_fal, use_container_width=True)

    # --- PÁGINAS TIENDA ---
    elif choice == "💰 Registrar Venta":
        st.header("🛒 Registro de Venta")
        with st.form("vta_form"):
            t_venta = st.selectbox("Selecciona tu Tienda", tiendas_lista)
            p_venta = st.text_input("Producto").upper()
            ta_venta = st.selectbox("Talla", ["S", "M", "L", "XL"])
            c_venta = st.number_input("Cantidad", min_value=1)
            pr_venta = st.number_input("Precio Total S/.", min_value=0.0)
            if st.form_submit_button("Finalizar Venta"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ventas (tienda, producto, talla, cantidad, precio) VALUES (:ti, :p, :t, :c, :pr)"),
                              {"ti":t_venta, "p":p_venta, "t":ta_venta, "c":c_venta, "pr":pr_venta})
                    s.commit()
                st.success("Venta guardada")

    elif choice == "🚨 Reportar Fallado":
        st.header("🚨 Reporte de Mercadería Fallada")
        with st.form("fall_form"):
            t_f = st.selectbox("Tienda", tiendas_lista)
            p_f = st.text_input("Producto con falla").upper()
            ta_f = st.selectbox("Talla", ["S", "M", "L", "XL"])
            c_f = st.number_input("Cantidad", min_value=1)
            mot_f = st.text_area("Describa la falla")
            st.info("Nota: Para fotos, subir a Google Drive y pegar el link en la descripción.")
            if st.form_submit_button("Enviar Reporte"):
                with conn.session as s:
                    s.execute(text("INSERT INTO fallados (tienda, producto, talla, cantidad, motivo) VALUES (:ti, :p, :t, :c, :m)"),
                              {"ti":t_f, "p":p_f, "t":ta_f, "c":c_f, "m":mot_f})
                    s.commit()
                st.success("Reporte enviado al administrador")
