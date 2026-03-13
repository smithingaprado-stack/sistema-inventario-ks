import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import plotly.express as px

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="KS CLOTHING - Sistema Integral", layout="wide", initial_sidebar_state="expanded")

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #000000; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- VARIABLES GLOBALES ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL", "XXL"]
CATEGORIAS = ["Hoodies", "Polos", "Pantalones", "Gorras", "Accesorios"]

# --- CONEXIÓN A BASE DE DATOS ---
conn = st.connection("postgresql", type="sql")

def inicializar_db():
    """Crea la estructura completa de la base de datos si no existe."""
    try:
        with conn.session as s:
            s.execute(text('CREATE TABLE IF NOT EXISTS ingresos (id SERIAL PRIMARY KEY, producto TEXT, categoria TEXT, talla TEXT, cantidad INTEGER, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS distribucion (id SERIAL PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
            s.execute(text('CREATE TABLE IF NOT EXISTS ventas (id SERIAL PRIMARY KEY, tienda TEXT, producto TEXT, categoria TEXT, talla TEXT, cantidad INTEGER, precio FLOAT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'))
            s.commit()
    except Exception as e:
        st.error(f"Error de conexión: {e}")

inicializar_db()

# --- FUNCIONES DE CONSULTA ---
def cargar_datos(tabla):
    return conn.query(f"SELECT * FROM {tabla} ORDER BY fecha DESC", ttl=0)

def obtener_stock_total():
    df_in = conn.query('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla')
    df_dist = conn.query('SELECT producto, talla, SUM(cantidad) as total_dist FROM distribucion GROUP BY producto, talla')
    
    if df_in.empty:
        return pd.DataFrame(columns=['producto', 'talla', 'Stock Almacén'])
    
    df = pd.merge(df_in, df_out := df_dist if not df_dist.empty else pd.DataFrame(columns=['producto','talla','total_dist']), 
                  on=['producto', 'talla'], how='left').fillna(0)
    
    df['Stock Almacén'] = df['total_in'] - df.get('total_dist', 0)
    return df

# --- SISTEMA DE LOGUEO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.rol = None

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("https://via.placeholder.com/150?text=KS+CLOTHING", width=150) # Puedes cambiar por tu logo
        st.title("🔐 KS CLOTHING - Acceso")
        pin = st.text_input("Ingrese su PIN de Seguridad", type="password")
        if st.button("Ingresar al Sistema"):
            if pin == "2026":
                st.session_state.autenticado = True
                st.session_state.rol = "Administrador"
                st.rerun()
            elif pin == "1234":
                st.session_state.autenticado = True
                st.session_state.rol = "Tienda"
                st.rerun()
            else:
                st.error("PIN incorrecto. Intente de nuevo.")
else:
    # --- MENÚ LATERAL ---
    st.sidebar.title(f"👤 {st.session_state.rol}")
    
    if st.session_state.rol == "Administrador":
        opciones = ["📊 Dashboard General", "📥 Ingreso Almacén", "🚚 Distribución", "💰 Registro Ventas", "📜 Historial Completo", "⚙️ Gestión de Datos"]
    else:
        opciones = ["💰 Registro Ventas", "📜 Mis Ventas Diarias"]
        
    menu = st.sidebar.radio("Seleccione una opción:", opciones)
    
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    # --- LÓGICA DE PÁGINAS ---

    if menu == "📊 Dashboard General":
        st.title("📊 Panel de Control KS")
        df_stock = obtener_stock_total()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Modelos en Almacén", len(df_stock['producto'].unique()) if not df_stock.empty else 0)
        with col2:
            st.metric("Prendas Totales", int(df_stock['Stock Almacén'].sum()) if not df_stock.empty else 0)
        with col3:
            df_v = cargar_datos("ventas")
            st.metric("Ventas Totales (S/.)", f"{df_v['precio'].sum():.2f}" if not df_v.empty else "0.00")

        if not df_stock.empty:
            st.subheader("📦 Inventario Actual en Almacén Central")
            st.dataframe(df_stock[['producto', 'talla', 'Stock Almacén']], use_container_width=True)
            
            fig = px.bar(df_stock, x="producto", y="Stock Almacén", color="talla", title="Distribución de Stock por Talla")
            st.plotly_chart(fig, use_container_width=True)

    elif menu == "📥 Ingreso Almacén":
        st.title("📥 Ingreso de Nueva Mercadería")
        with st.form("form_ingreso", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                prod = st.text_input("Nombre del Producto").upper()
                cat = st.selectbox("Categoría", CATEGORIAS)
            with col2:
                tall = st.selectbox("Talla", TALLAS)
                cant = st.number_input("Cantidad", min_value=1, step=1)
            
            if st.form_submit_button("Registrar Ingreso"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ingresos (producto, categoria, talla, cantidad) VALUES (:p, :c, :t, :can)"),
                              {"p": prod, "c": cat, "t": tall, "can": cant})
                    s.commit()
                st.success(f"Se han ingresado {cant} unidades de {prod} al almacén.")

    elif menu == "🚚 Distribución":
        st.title("🚚 Enviar Mercadería a Tiendas")
        df_s = obtener_stock_total()
        if df_s.empty or df_s['Stock Almacén'].sum() == 0:
            st.warning("No hay mercadería en el almacén central para distribuir.")
        else:
            with st.form("form_dist"):
                prod_sel = st.selectbox("Seleccione Producto", df_s['producto'].unique())
                tallas_disponibles = df_s[df_s['producto'] == prod_sel]['talla'].unique()
                talla_sel = st.selectbox("Seleccione Talla", tallas_disponibles)
                tienda_dest = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                
                stock_max = int(df_s[(df_s['producto'] == prod_sel) & (df_s['talla'] == talla_sel)]['Stock Almacén'].values[0])
                st.info(f"Stock disponible: {stock_max}")
                cant_env = st.number_input("Cantidad a enviar", min_value=1, max_value=stock_max)
                
                if st.form_submit_button("Confirmar Envío"):
                    with conn.session as s:
                        s.execute(text("INSERT INTO distribucion (producto, talla, cantidad, tienda) VALUES (:p, :t, :c, :ti)"),
                                  {"p": prod_sel, "t": talla_sel, "c": cant_env, "ti": tienda_dest})
                        s.commit()
                    st.success("Distribución realizada con éxito.")
                    st.rerun()

    elif menu == "💰 Registro Ventas":
        st.title("💰 Registro de Ventas")
        with st.form("form_ventas", clear_on_submit=True):
            tienda_v = st.selectbox("Tienda", NOMBRES_TIENDAS)
            prod_v = st.text_input("Producto Vendido").upper()
            col1, col2, col3 = st.columns(3)
            with col1: tall_v = st.selectbox("Talla", TALLAS)
            with col2: cant_v = st.number_input("Cantidad", min_value=1)
            with col3: precio_v = st.number_input("Precio Unitario (S/.)", min_value=0.0)
            
            if st.form_submit_button("Registrar Venta"):
                with conn.session as s:
                    s.execute(text("INSERT INTO ventas (tienda, producto, talla, cantidad, precio) VALUES (:ti, :p, :t, :c, :pr)"),
                              {"ti": tienda_v, "p": prod_v, "t": tall_v, "c": cant_v, "pr": precio_v})
                    s.commit()
                st.success("Venta guardada correctamente.")

    elif menu == "📜 Historial Completo":
        st.title("📜 Historial de Movimientos")
        tab1, tab2, tab3 = st.tabs(["Ingresos", "Distribución", "Ventas"])
        
        with tab1:
            st.dataframe(cargar_datos("ingresos"), use_container_width=True)
        with tab2:
            st.dataframe(cargar_datos("distribucion"), use_container_width=True)
        with tab3:
            st.dataframe(cargar_datos("ventas"), use_container_width=True)

    elif menu == "⚙️ Gestión de Datos":
        st.title("⚙️ Administración de la Base de Datos")
        st.warning("CUIDADO: Estas acciones son irreversibles.")
        
        tabla_del = st.selectbox("Seleccione tabla para limpiar historial", ["ingresos", "distribucion", "ventas"])
        confirm = st.text_input(f"Escriba 'BORRAR {tabla_del.upper()}' para confirmar")
        
        if st.button("Limpiar Tabla Seleccionada"):
            if confirm == f"BORRAR {tabla_del.upper()}":
                with conn.session as s:
                    s.execute(text(f"TRUNCATE TABLE {tabla_del} RESTART IDENTITY"))
                    s.commit()
                st.error(f"La tabla {tabla_del} ha sido vaciada.")
                st.rerun()
