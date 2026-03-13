import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- CONFIGURACIÓN ---
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# --- CONEXIÓN PERMANENTE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def leer_datos(pestaña):
    try:
        return conn.read(worksheet=pestaña, ttl="0")
    except:
        return pd.DataFrame()

# --- CÁLCULO DE STOCK ---
def obtener_stock_real():
    df_in = leer_datos("Ingresos")
    df_out = leer_datos("Distribucion")
    if df_in.empty:
        return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    res_in = df_in.groupby(['producto', 'talla'])['cantidad'].sum().reset_index()
    res_out = df_out.groupby(['producto', 'talla'])['cantidad'].sum().reset_index() if not df_out.empty else pd.DataFrame(columns=['producto', 'talla', 'cantidad'])
    df = pd.merge(res_in, res_out, on=['producto', 'talla'], how='left', suffixes=('_in', '_out')).fillna(0)
    df['stock_disponible'] = df['cantidad_in'] - df['cantidad_out']
    return df[df['stock_disponible'] > 0]

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema KS - Control Total", layout="wide")

if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso al Sistema KS")
    pin = st.text_input("Introduce tu PIN", type="password")
    if st.button("Ingresar"):
        if pin == "2026":
            st.session_state['rol'] = "admin"; st.rerun()
        elif pin == "1234":
            st.session_state['rol'] = "tienda"; st.rerun()
        else:
            st.error("PIN Incorrecto")
else:
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 MODO ADMINISTRADOR")
        menu = ["📊 Inventario Central", "📥 Ingreso Almacén", "🚚 Enviar a Tiendas", "📈 Ventas Globales", "📦 Pedidos Recibidos"]
    else:
        st.sidebar.info("🏪 MODO TIENDA")
        menu = ["🛒 Registrar Venta", "📜 Historial y Editar", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Seleccione opción:", menu)

    # --- TIENDA ---
    if choice == "🛒 Registrar Venta":
        st.header("🛒 Registrar Venta Diaria")
        with st.form("form_venta", clear_on_submit=True):
            tienda_v = st.selectbox("Tu Tienda", NOMBRES_TIENDAS)
            prod_v = st.text_input("Producto").upper()
            talla_v = st.selectbox("Talla", TALLAS)
            cant_v = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Confirmar Venta"):
                df_v = leer_datos("Ventas")
                nueva_v = pd.DataFrame([[tienda_v, prod_v, talla_v, cant_v, datetime.now().strftime("%Y-%m-%d")]], columns=['tienda', 'producto', 'talla', 'cantidad', 'fecha'])
                conn.update(worksheet="Ventas", data=pd.concat([df_v, nueva_v], ignore_index=True))
                st.success("✅ Venta guardada")

    elif choice == "📜 Historial y Editar":
        st.header("📜 Historial de Ventas")
        df_v = leer_datos("Ventas")
        if not df_v.empty:
            st.dataframe(df_v, use_container_width=True)
            st.info("Para editar, borra la fila en tu Google Sheet.")

    elif choice == "📝 Hacer Pedido":
        st.header("📝 Solicitar Mercadería")
        with st.form("form_ped", clear_on_submit=True):
            t_ped = st.selectbox("Tienda", NOMBRES_TIENDAS)
            txt = st.text_area("Lista de faltantes...")
            if st.form_submit_button("Enviar Pedido"):
                df_p = leer_datos("Pedidos")
                nuevo_p = pd.DataFrame([[t_ped, txt, datetime.now().strftime("%Y-%m-%d %H:%M")]], columns=['tienda', 'pedido', 'fecha'])
                conn.update(worksheet="Pedidos", data=pd.concat([df_p, nuevo_p], ignore_index=True))
                st.success("🚀 Pedido enviado")

    # --- ADMIN ---
    elif choice == "📊 Inventario Central":
        st.header("📊 Stock Real")
        st.dataframe(obtener_stock_real(), use_container_width=True)

    elif choice == "📥 Ingreso Almacén":
        st.header("📥 Entrada de Mercadería")
        with st.form("form_in", clear_on_submit=True):
            p = st.text_input("Producto").upper()
            t = st.selectbox("Talla", TALLAS)
            c = st.number_input("Cantidad", min_value=1, step=1)
            if st.form_submit_button("Guardar"):
                df_in = leer_datos("Ingresos")
                nuevo_in = pd.DataFrame([[p, t, c, datetime.now().strftime("%Y-%m-%d")]], columns=['producto', 'talla', 'cantidad', 'fecha'])
                conn.update(worksheet="Ingresos", data=pd.concat([df_in, nuevo_in], ignore_index=True))
                st.success("📦 Stock actualizado")

    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Enviar a Sucursales")
        df_inv = obtener_stock_real()
        if not df_inv.empty:
            with st.form("form_env", clear_on_submit=True):
                p_s = st.selectbox("Producto", df_inv['producto'].unique())
                t_s = st.selectbox("Talla", TALLAS)
                dest = st.selectbox("Destino", NOMBRES_TIENDAS)
                cant = st.number_input("Cantidad", min_value=1)
                if st.form_submit_button("Confirmar Envío"):
                    df_out = leer_datos("Distribucion")
                    nuevo_out = pd.DataFrame([[p_s, t_s, cant, dest, datetime.now().strftime("%Y-%m-%d")]], columns=['producto', 'talla', 'cantidad', 'tienda', 'fecha'])
                    conn.update(worksheet="Distribucion", data=pd.concat([df_out, nuevo_out], ignore_index=True))
                    st.success("🚚 Mercadería enviada")
                    st.rerun()

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None
        st.rerun()
