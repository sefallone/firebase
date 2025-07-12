import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Configuración inicial
st.set_page_config(page_title="Sistema de Inventario", layout="wide")
st.title("📦 Sistema de Gestión de Inventario")

# Configuración de la base de datos
DB_FILE = "inventario.db"

# ------------------------------------------
# FUNCIONES DE BASE DE DATOS MEJORADAS
# ------------------------------------------

def init_db():
    """Inicializa la base de datos con manejo de errores"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            precio REAL NOT NULL,
            costo REAL NOT NULL,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_connection():
    """Obtiene una conexión a la base de datos"""
    return sqlite3.connect(DB_FILE)

def ejecutar_consulta(query, params=()):
    """Ejecuta una consulta SQL con manejo de errores"""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"Error de base de datos: {str(e)}")
        return False
    finally:
        conn.close()

def obtener_productos():
    """Obtiene todos los productos y actualiza el estado"""
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM productos ORDER BY nombre", conn)
        # Actualizar el estado de la aplicación
        st.session_state.productos_df = df
        return df
    finally:
        conn.close()

# ------------------------------------------
# FUNCIONES PRINCIPALES CON ACTUALIZACIÓN
# ------------------------------------------

def agregar_producto(nombre, stock, precio, costo):
    """Agrega un nuevo producto y actualiza el estado"""
    if ejecutar_consulta(
        "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
        (nombre, stock, precio, costo)
    ):
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    return False

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza un producto y fuerza la actualización"""
    if ejecutar_consulta(
        "UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
        (nombre, stock, precio, costo, id_producto)
    ):
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    return False

# ------------------------------------------
# INTERFAZ DE USUARIO CON ACTUALIZACIÓN
# ------------------------------------------

def mostrar_inventario():
    """Muestra el inventario con actualización automática"""
    # Verificar si necesitamos actualizar
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
    # Obtener productos (actualiza el estado automáticamente)
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos registrados.")
        return
    
    # Calcular valores adicionales
    productos['Valor Total'] = productos['stock'] * productos['precio']
    productos['Costo Total'] = productos['stock'] * productos['costo']
    productos['Margen'] = productos['precio'] - productos['costo']
    productos['Margen %'] = (productos['Margen'] / productos['precio'] * 100).round(2)
    
    # Mostrar tabla con formato
    st.dataframe(
        productos.style.format({
            'precio': '${:,.2f}',
            'costo': '${:,.2f}',
            'Valor Total': '${:,.2f}',
            'Costo Total': '${:,.2f}',
            'Margen': '${:,.2f}',
            'Margen %': '{:.2f}%'
        }),
        use_container_width=True
    )

def mostrar_formulario_agregar():
    """Formulario para agregar productos"""
    st.header("➕ Agregar Nuevo Producto")
    
    with st.form("form_agregar", clear_on_submit=True):
        nombre = st.text_input("Nombre del Producto*")
        col1, col2 = st.columns(2)
        stock = col1.number_input("Stock Inicial*", min_value=0, value=0)
        precio = col1.number_input("Precio de Venta*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        costo = col2.number_input("Costo del Producto*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        if st.form_submit_button("Agregar Producto"):
            if not nombre:
                st.error("El nombre del producto es obligatorio")
                return
                
            if precio <= 0 or costo < 0:
                st.error("Precio y costo deben ser valores positivos")
                return
                
            if agregar_producto(nombre, stock, precio, costo):
                st.success("¡Producto agregado correctamente!")
                st.experimental_rerun()

def mostrar_formulario_editar():
    """Formulario para editar productos con actualización"""
    st.header("✏️ Editar Producto")
    
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos para editar")
        return
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        productos['nombre'],
        key="select_editar"
    )
    
    producto = productos[productos['nombre'] == producto_seleccionado].iloc[0]
    
    with st.form("form_editar"):
        nuevo_nombre = st.text_input("Nombre*", value=producto['nombre'], key="nombre_edit")
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input("Stock*", min_value=0, value=producto['stock'], key="stock_edit")
        nuevo_precio = col1.number_input("Precio*", min_value=0.0, value=producto['precio'], step=0.01, format="%.2f", key="precio_edit")
        nuevo_costo = col2.number_input("Costo*", min_value=0.0, value=producto['costo'], step=0.01, format="%.2f", key="costo_edit")
        
        if st.form_submit_button("Actualizar Producto"):
            if not nuevo_nombre:
                st.error("El nombre del producto es obligatorio")
                return
                
            if nuevo_precio <= 0 or nuevo_costo < 0:
                st.error("Precio y costo deben ser valores positivos")
                return
                
            if actualizar_producto(producto['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
                st.success("¡Producto actualizado correctamente!")
                st.experimental_rerun()

# ------------------------------------------
# CONFIGURACIÓN PRINCIPAL
# ------------------------------------------

def main():
    # Inicializar la base de datos
    init_db()
    
    # Inicializar estado si no existe
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
    # Menú de opciones
    menu_options = {
        "Ver Inventario": mostrar_inventario,
        "Agregar Producto": mostrar_formulario_agregar,
        "Editar Producto": mostrar_formulario_editar
    }
    
    with st.sidebar:
        st.title("Menú Principal")
        selected = st.radio(
            "Seleccione una opción:",
            list(menu_options.keys()),
            key="main_menu"
        )
    
    # Mostrar la opción seleccionada
    menu_options[selected]()

if __name__ == "__main__":
    main()
