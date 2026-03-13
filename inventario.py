import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# =========================================================
# 1. CONFIGURACIÓN INICIAL Y ESTILOS
# =========================================================
st.set_page_config(
    page_title="Sistema KS - Control Maestro",
    page_icon="🧥",
    layout="wide"
)

# Definición de constantes para evitar errores de escritura
NOMBRES_TIENDAS = ["Tienda Central", "Tienda Norte", "Tienda Sur", "Tienda Este", "Tienda Oeste"]
TALLAS = ["S", "M", "L", "XL"]

# =========================================================
# 2. CONEXIÓN A GOOGLE SHEETS (BASE DE DATOS ETERNA)
# =========================================================
# Esta conexión permite que los datos NO SE BORREN al cerrar la web
conn = st.connection("gsheets", type=GSheetsConnection)

def leer_datos(pestaña):
    """Lee datos en tiempo real de Google Sheets."""
    try:
        # ttl=0 asegura que siempre lea lo más nuevo, no lo guardado en memoria
        return conn.read(worksheet=pestaña, ttl=0)
    except Exception:
        # Si la pestaña no existe aún, devuelve un DataFrame vacío con columnas
        if pestaña == "Ingresos":
            return pd.DataFrame(columns=['producto', 'talla', 'cantidad', 'fecha'])
        if pestaña == "Distribucion":
            return pd.DataFrame(columns=['producto', 'talla', 'cantidad', 'tienda', 'fecha'])
        if pestaña == "Ventas":
            return pd.DataFrame(columns=['tienda', 'producto', 'talla', 'cantidad', 'fecha'])
        if pestaña == "Pedidos":
            return pd.DataFrame(columns=['tienda', 'pedido', 'fecha'])
        return pd.DataFrame()

# =========================================================
# 3. LÓGICA MATEMÁTICA (RESTA DE STOCK)
# =========================================================
def obtener_stock_real():
    """Calcula el stock disponible: Ingresos menos lo enviado a tiendas."""
    df_in = leer_datos("Ingresos")
    df_out = leer_datos("Distribucion")
    
    if df_in.empty:
        return pd.DataFrame(columns=['producto', 'talla', 'stock_disponible'])
    
    # Agrupar ingresos por producto y talla
    res_in = df_in.groupby(['producto', 'talla'])['cantidad'].sum().reset_index()
    
    # Agrupar salidas por producto y talla
    if not df_out.empty:
        res_out = df_out.groupby(['producto', 'talla'])['cantidad'].sum().reset_index()
    else:
        res_out = pd.DataFrame(columns=['producto', 'talla', 'cantidad'])
    
    # Unir tablas y calcular resta
    df_merge = pd.merge(res_in, res_out, on=['producto', 'talla'], how='left', suffixes=('_in', '_out')).fillna(0)
    df_merge['stock_disponible'] = df_merge['cantidad_in'] - df_merge['cantidad_out']
    
    return df_merge[df_merge['stock_disponible'] > 0]

# =========================================================
# 4. CONTROL DE ACCESO (LOGIN POR PIN)
# =========================================================
if 'rol' not in st.session_state:
    st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🛡️ Acceso de Seguridad - Sistema KS")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pin = st.text_input("Ingrese su PIN para continuar", type="password")
        if st.button("🔓 Entrar al Sistema"):
            if pin == "2026":
                st.session_state['rol'] = "admin"
                st.rerun()
            elif pin == "1234":
                st.session_state['rol'] = "tienda"
                st.rerun()
            else:
                st.error("❌ PIN incorrecto. Acceso denegado.")
else:
    # =========================================================
    # 5. MENÚ LATERAL Y NAVEGACIÓN
    # =========================================================
    st.sidebar.title("MENU PRINCIPAL")
    
    if st.session_state['rol'] == "admin":
        st.sidebar.success("✅ MODO: ADMINISTRADOR")
        menu = [
            "📊 Inventario Real", 
            "📥 Registrar Ingreso Almacén", 
            "🚚 Enviar Mercadería a Sucursal", 
            "📈 Reporte de Ventas Global", 
            "📦 Revisar Pedidos de Tiendas"
        ]
    else:
        st.sidebar.info("🏪 MODO: TIENDA")
        menu = [
            "🛒 Registrar Venta Diaria", 
            "📜 Historial de Ventas (Editar)", 
            "📝 Solicitar Pedido al Jefe"
        ]
    
    choice = st.sidebar.selectbox("Seleccione una operación:", menu)
    st.sidebar.markdown("---")

    # ---------------------------------------------------------
    # SECCIÓN ADMIN: INVENTARIO
    # ---------------------------------------------------------
    if choice == "📊 Inventario Real":
        st.header("📊 Stock Disponible en Almacén Central")
        df_stock = obtener_stock_real()
        if not df_stock.empty:
            st.dataframe(df_stock, use_container_width=True)
            # Gráfico rápido de stock
            st.bar_chart(data=df_stock, x="producto", y="stock_disponible")
        else:
            st.info("No hay productos registrados en el inventario.")

    # ---------------------------------------------------------
    # SECCIÓN ADMIN: REGISTRAR INGRESO
    # ---------------------------------------------------------
    elif choice == "📥 Registrar Ingreso Almacén":
        st.header("📥 Entrada de Nueva Mercadería")
        with st.form("form_ingreso", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                prod = st.text_input("Nombre del Producto (Ej: HOODIE GOTHIC)").upper()
                talla = st.selectbox("Talla", TALLAS)
            with col_b:
                cant = st.number_input("Cantidad de unidades", min_value=1, step=1)
                fecha = st.date_input("Fecha de ingreso", datetime.now())
            
            if st.form_submit_button("Guardar en Google Sheets"):
                df_actual = leer_datos("Ingresos")
                nueva_fila = pd.DataFrame([[prod, talla, cant, str(fecha)]], 
                                         columns=['producto', 'talla', 'cantidad', 'fecha'])
                df_final = pd.concat([df_actual, nueva_fila], ignore_index=True)
                conn.update(worksheet="Ingresos", data=df_final)
                st.success(f"✅ ¡{prod} registrado con éxito en la nube!")

    # ---------------------------------------------------------
    # SECCIÓN ADMIN: ENVIAR A TIENDAS
    # ---------------------------------------------------------
    elif choice == "🚚 Enviar Mercadería a Sucursal":
        st.header("🚚 Distribución a Tiendas")
        df_inv = obtener_stock_real()
        if not df_inv.empty:
            with st.form("form_envio", clear_on_submit=True):
                prod_env = st.selectbox("Seleccionar Producto", df_inv['producto'].unique())
                talla_env = st.selectbox("Seleccionar Talla", TALLAS)
                tienda_dest = st.selectbox("Tienda Destino", NOMBRES_TIENDAS)
                cant_env = st.number_input("Cantidad a enviar", min_value=1)
                
                if st.form_submit_button("Confirmar Envío"):
                    df_dist = leer_datos("Distribucion")
                    envio_nuevo = pd.DataFrame([[prod_env, talla_env, cant_env, tienda_dest, datetime.now().strftime("%Y-%m-%d")]], 
                                              columns=['producto', 'talla', 'cantidad', 'tienda', 'fecha'])
                    df_final = pd.concat([df_dist, envio_nuevo], ignore_index=True)
                    conn.update(worksheet="Distribucion", data=df_final)
                    st.success(f"🚚 Mercadería enviada a {tienda_dest}")
                    st.rerun()
        else:
            st.warning("⚠️ No hay stock disponible para realizar envíos.")

    # ---------------------------------------------------------
    # SECCIÓN TIENDA: REGISTRAR VENTA
    # ---------------------------------------------------------
    elif choice == "🛒 Registrar Venta Diaria":
        st.header("🛒 Registro de Venta")
        with st.form("form_v_tienda", clear_on_submit=True):
            t_origen = st.selectbox("Tu Sucursal", NOMBRES_TIENDAS)
            p_vendido = st.text_input("Producto Vendido").upper()
            ta_vendida = st.selectbox("Talla", TALLAS)
            ca_vendida = st.number_input("Cantidad", min_value=1)
            
            if st.form_submit_button("Registrar Venta"):
                df_v = leer_datos("Ventas")
                v_nueva = pd.DataFrame([[t_origen, p_vendido, ta_vendida, ca_vendida, datetime.now().strftime("%Y-%m-%d")]], 
                                      columns=['tienda', 'producto', 'talla', 'cantidad', 'fecha'])
                df_actualizado = pd.concat([df_v, v_nueva], ignore_index=True)
                conn.update(worksheet="Ventas", data=df_actualizado)
                st.success("✅ Venta guardada correctamente.")

    # ---------------------------------------------------------
    # SECCIÓN TIENDA: HISTORIAL / EDITAR
    # ---------------------------------------------------------
    elif choice == "📜 Historial de Ventas (Editar)":
        st.header("📜 Mis Ventas Registradas")
        t_hist = st.selectbox("Selecciona tu tienda para filtrar", NOMBRES_TIENDAS)
        df_ventas = leer_datos("Ventas
