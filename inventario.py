import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF
import base64

# --- BASE DE DATOS ---
def get_connection():
    return sqlite3.connect('ks_sistema_pro_v8.db', check_same_thread=False)

def crear_tablas():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS distribucion (id INTEGER PRIMARY KEY, producto TEXT, talla TEXT, cantidad INTEGER, tienda TEXT, fecha DATE, estado TEXT DEFAULT "pendiente")')
    c.execute('CREATE TABLE IF NOT EXISTS ventas_tiendas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, fecha DATE)')
    c.execute('CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY, tienda TEXT, pedido_texto TEXT, foto BLOB, fecha DATETIME)')
    c.execute('CREATE TABLE IF NOT EXISTS fallas (id INTEGER PRIMARY KEY, tienda TEXT, producto TEXT, talla TEXT, cantidad INTEGER, motivo TEXT, fecha DATE)')
    # TABLA PARA NOMBRES DE TIENDAS
    c.execute('CREATE TABLE IF NOT EXISTS lista_tiendas (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE)')
    
    # Insertar tiendas iniciales si la tabla está vacía
    c.execute('SELECT COUNT(*) FROM lista_tiendas')
    if c.fetchone()[0] == 0:
        tiendas_iniciales = [("Tienda Central",), ("Tienda Norte",), ("Tienda Sur",)]
        c.executemany('INSERT INTO lista_tiendas (nombre) VALUES (?)', tiendas_iniciales)
    
    conn.commit()
    conn.close()

crear_tablas()

# --- FUNCIONES DE TIENDAS ---
def obtener_nombres_tiendas():
    conn = get_connection()
    df = pd.read_sql('SELECT nombre FROM lista_tiendas', conn)
    conn.close()
    return df['nombre'].tolist()

# --- GENERADOR DE PDF ---
def generar_pdf(tienda, producto, talla, cantidad):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="GUIA DE REMISION - KS CLOTHING", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.cell(200, 10, txt=f"Destino: {tienda}", ln=True)
    pdf.ln(5)
    pdf.cell(200, 10, txt=f"PRODUCTO: {producto}", ln=True)
    pdf.cell(200, 10, txt=f"TALLA: {talla}", ln=True)
    pdf.cell(200, 10, txt=f"CANTIDAD: {cantidad} unidades", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- CONFIGURACIÓN APP ---
st.set_page_config(page_title="KS Pro - Personalizado", layout="wide")
TALLAS = ["S", "M", "L", "XL"]
STOCK_MINIMO = 5

if 'rol' not in st.session_state: st.session_state['rol'] = None

if st.session_state['rol'] is None:
    st.title("🔐 Acceso Sistema KS")
    pin = st.text_input("PIN", type="password")
    if st.button("Ingresar"):
        if pin == "2026": st.session_state['rol'] = "admin"; st.rerun()
        elif pin == "1234": st.session_state['rol'] = "tienda"; st.rerun()
        else: st.error("PIN Incorrecto")
else:
    mis_tiendas = obtener_nombres_tiendas()
    
    if st.session_state['rol'] == "admin":
        st.sidebar.success("💻 ADMINISTRADOR")
        menu = ["📊 Dashboard", "📥 Ingresar Mercadería", "🚚 Enviar a Tiendas", "📦 Pedidos", "⚙️ Configuración Tiendas"]
    else:
        st.sidebar.info("🏪 TIENDA")
        menu = ["🎁 Recibir Envío", "🛒 Registrar Venta", "⚠️ Reportar Falla", "📝 Hacer Pedido"]
    
    choice = st.sidebar.selectbox("Ir a:", menu)

    # --- NUEVA SECCIÓN: CONFIGURACIÓN DE TIENDAS (SOLO ADMIN) ---
    if choice == "⚙️ Configuración Tiendas":
        st.header("⚙️ Administrar Nombres de Tiendas")
        
        col1, col2 = st.columns(2)
        with col1:
            nueva_t = st.text_input("Nombre de la nueva tienda")
            if st.button("Añadir Tienda"):
                if nueva_t:
                    conn = get_connection()
                    try:
                        conn.execute('INSERT INTO lista_tiendas (nombre) VALUES (?)', (nueva_t,))
                        conn.commit()
                        st.success(f"Tienda '{nueva_t}' añadida.")
                        st.rerun()
                    except: st.error("Ese nombre ya existe.")
                    finally: conn.close()
        
        with col2:
            st.write("### Tiendas actuales")
            for t in mis_tiendas:
                c1, c2 = st.columns([3, 1])
                c1.write(t)
                if c2.button("Eliminar", key=f"del_{t}"):
                    conn = get_connection()
                    conn.execute('DELETE FROM lista_tiendas WHERE nombre=?', (t,))
                    conn.commit()
                    conn.close()
                    st.rerun()

    # --- ENVIAR A TIENDAS (Usando nombres dinámicos) ---
    elif choice == "🚚 Enviar a Tiendas":
        st.header("🚚 Enviar Mercadería")
        conn = get_connection()
        ingresos = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_in FROM ingresos GROUP BY producto, talla', conn)
        salidas = pd.read_sql('SELECT producto, talla, SUM(cantidad) as total_out FROM distribucion GROUP BY producto, talla', conn)
        conn.close()
        
        df_stock = pd.merge(ingresos, salidas, on=['producto', 'talla'], how='left').fillna(0)
        df_stock['stock'] = df_stock['total_in'] - df_stock['total_out']
        df_stock = df_stock[df_stock['stock'] > 0]

        if not df_stock.empty:
            with st.form("env"):
                p_s = st.selectbox("Producto", df_stock['producto'].unique())
                t_s = st.selectbox("Talla", TALLAS)
                d = st.selectbox("Tienda Destino", mis_tiendas) # Nombres dinámicos
                cn = st.number_input("Cant", min_value=1)
                if st.form_submit_button("Enviar"):
                    conn = get_connection()
                    conn.execute('INSERT INTO distribucion (producto, talla, cantidad, tienda, fecha) VALUES (?,?,?,?,?)', (p_s, t_s, cn, d, datetime.now().date()))
                    conn.commit(); conn.close()
                    st.success("Enviado")
                    pdf = generar_pdf(d, p_s, t_s, cn)
                    st.download_button("📄 Bajar Guía PDF", pdf, file_name=f"guia_{d}.pdf")
        else: st.warning("No hay stock.")

    # --- LÓGICA RESTANTE (Resumida para que el código no sea infinito) ---
    elif choice == "📊 Dashboard":
        st.header("📊 Stock Central")
        # Aquí va la lógica de mostrar el inventario (mantenla igual que el anterior)
        st.info("Aquí verás tus alertas de stock bajo y tablas.")

    # (El resto de funciones: Recibir Envío, Registrar Venta, Pedidos, etc. 
    #  ahora usarán automáticamente la lista 'mis_tiendas' actualizada)

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['rol'] = None; st.rerun()
