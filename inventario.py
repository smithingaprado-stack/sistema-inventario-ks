import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="KS CLOTHING - Sistema Profesional", layout="wide")

# --- CONEXIÓN A BASE DE DATOS ---
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    try:
        with conn.session as s:
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, categoria TEXT, talla TEXT, cantidad INTEGER, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, precio FLOAT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
            s.commit()
    except: pass

inicializar_db()

# --- CONSTANTES ---
TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL", "XXL"]
CATEGORIAS = ["Hoodies", "Polos", "Pantalones", "Gorras"]

# --- LÓGICA DE STOCK ---
def obtener_datos(tabla):
    return conn.query(f"SELECT * FROM {tabla} ORDER BY fecha DESC", ttl=0)

def obtener_stock_central():
    df_in = conn.query('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla')
    df_dist = conn.query('SELECT producto, talla, SUM(cantidad) as total_dist FROM distribucion GROUP BY producto, talla')
    if df_in.empty: return pd.DataFrame(columns=['producto', 'talla', 'Disponible'])
    df = pd.merge(df_in, df_dist if not df_dist.empty else pd.DataFrame(columns=['producto','talla','total_dist']), on=['producto', 'talla'], how='left').fillna(0)
    df['Disponible'] = df['total_in'] - df.get('total_dist', 0)
    return df[df['Disponible'] > 0]

# --- LOGIN ---
if 'logueado' not in st.session_state:
    st.session_state.logueado = False
    st.session_state.rol = None

if not st.session_state.logueado:
    st.title("🔒 Sistema KS Clothing")
    pin = st.text_input("Ingrese su PIN de acceso", type="password")
    if st.button("Entrar"):
        if pin == "2026":
            st.session_state.logueado, st.session_state.rol = True, "ADMINISTRADOR"
            st.rerun()
        elif pin == "1234":
            st.session_state.logueado, st.session_state.rol = True, "TIENDA"
            st.rerun()
        else: st.error("PIN incorrecto")
else:
    st.sidebar.title(f"👤 {st.session_state.rol}")
    
    # --- INTERFAZ DE ADMINISTRADOR ---
    if st.session_state.rol == "ADMINISTRADOR":
        menu = st.sidebar.radio("Menú Principal", ["📊 Dashboard", "📥 Almacén Central", "🚚 Enviar a Tiendas", "💰 Ventas Globales", "📜 Historial y Edición", "⚙️ Ajustes"])

        if menu == "📊 Dashboard":
            st.header("📊 Resumen General KS")
            df_s = obtener_stock_central()
            col1, col2, col3 = st.columns(3)
            col1.metric("Modelos Activos", len(df_s['producto'].unique()) if not df_s.empty else 0)
            col2.metric("Prendas en Almacén", int(df_s['Disponible'].sum()) if not df_s.empty else 0)
            
            if not df_s.empty:
                fig = px.pie(df_s, values='Disponible', names='producto', title="Distribución de Inventario")
                st.plotly_chart(fig, use_container_width=True)

        elif menu == "📥 Almacén Central":
            st.subheader("📥 Carga de Mercadería Nueva")
            with st.form("carga"):
                p = st.text_input("Producto").upper()
                c = st.selectbox("Categoría", CATEGORIAS)
                t = st.selectbox("Talla", TALLAS)
                can = st.number_input("Cantidad", min_value=1)
                if st.form_submit_button("Registrar en Almacén"):
                    with conn.session as s:
                        s.execute(text("INSERT INTO ingresos (producto, categoria, talla, cantidad) VALUES (:p, :c, :t, :can)"), {"p":p,"c":c,"t":t,"can":can})
                        s.commit()
                    st.success("Cargado correctamente")

        elif menu == "🚚 Enviar a Tiendas":
            st.subheader("🚚 Distribución de Mercadería")
            df_s = obtener_stock_central()
            if not df_s.empty:
                with st.form("envio"):
                    prod = st.selectbox("Producto", df_s['producto'].unique())
                    talla = st.selectbox("Talla", df_s[df_s['producto']==prod]['talla'].unique())
                    tienda = st.selectbox("Tienda Destino", TIENDAS)
                    max_c = int(df_s[(df_s['producto']==prod)&(df_s['talla']==talla)]['Disponible'].values[0])
                    cant = st.number_input(f"Cantidad (Máx {max_c})", min_value=1, max_value=max_c)
                    if st.form_submit_button("Confirmar Envío"):
                        with conn.session as s:
                            s.execute(text("INSERT INTO distribucion (producto, talla, cantidad, tienda) VALUES (:p, :t, :c, :ti)"), {"p":prod,"t":talla,"c":cant,"ti":tienda})
                            s.commit()
                        st.success("Envío registrado")
                        st.rerun()

        elif menu == "📜 Historial y Edición":
            st.subheader("📜 Historial de Movimientos")
            tipo = st.selectbox("Ver tabla:", ["Ingresos Almacén", "Distribución Tiendas", "Ventas"])
            tabla_map = {"Ingresos Almacén": "ingresos", "Distribución Tiendas": "distribucion", "Ventas": "ventas"}
            df_h = obtener_datos(tabla_map[tipo])
            st.dataframe(df_h, use_container_width=True)
            
            st.divider()
            st.subheader("⚠️ Eliminar Registro por ID")
            id_del = st.number_input("Ingrese ID a borrar", min_value=1)
            if st.button("Confirmar Eliminación"):
                with conn.session as s:
                    s.execute(text(f"DELETE FROM {tabla_map[tipo]} WHERE id = :id"), {"id":id_del})
                    s.commit()
                st.error(f"Registro {id_del} eliminado de {tipo}")
                st.rerun()

    # --- INTERFAZ DE TIENDA ---
    else:
        menu = st.sidebar.radio("Menú Tienda", ["🛒 Registrar Venta", "📋 Mis Ventas Hoy", "📦 Stock en Almacén Central"])
        
        if menu == "🛒 Registrar Venta":
            st.header("🛒 Formulario de Venta")
            with st.form("venta_tienda"):
                tienda_v = st.selectbox("Mi Tienda", TIENDAS)
                prod_v = st.text_input("Producto").upper()
                talla_v = st.selectbox("Talla", TALLAS)
                cant_v = st.number_input("Cantidad", min_value=1)
                precio_v = st.number_input("Precio Final (S/.)", min_value=0.0)
                if st.form_submit_button("Finalizar Venta"):
                    with conn.session as s:
                        s.execute(text("INSERT INTO ventas (tienda, producto, talla, cantidad, precio) VALUES (:ti, :p, :t, :c, :pr)"),
                                  {"ti":tienda_v, "p":prod_v, "t":talla_v, "c":cant_v, "pr":precio_v})
                        s.commit()
                    st.success("Venta guardada")

        elif menu == "📦 Stock en Almacén Central":
            st.info("Consulte aquí qué hay disponible en el almacén principal para pedir reposición.")
            st.dataframe(obtener_stock_central(), use_container_width=True)

    if st.sidebar.button("Salir"):
        st.session_state.logueado = False
        st.rerun()
