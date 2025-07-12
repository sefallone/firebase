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
# FUNCIONES DE BASE DE DATOS (Mantenemos las últimas versiones correctas)
# ------------------------------------------

def init_db():
    """Inicializa la base de datos con las tablas necesarias"""
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
    """Ejecuta una consulta SQL con manejo de errores (para operaciones que no requieren transacción compleja)"""
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
    """Obtiene todos los productos como DataFrame"""
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM productos ORDER BY nombre", conn)
        return df
    finally:
        conn.close()

def agregar_producto(nombre, stock, precio, costo):
    """Agrega un nuevo producto a la base de datos, con verificación de duplicados."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM productos WHERE nombre=?", (nombre,))
        if c.fetchone()[0] > 0:
            st.error(f"Ya existe un producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
            return False
            
        c.execute("INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
                  (nombre, stock, precio, costo))
        conn.commit()
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except sqlite3.Error as e:
        st.error(f"Error de base de datos al agregar producto: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza los datos de un producto existente, con verificación de duplicados."""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM productos WHERE nombre=? AND id != ?", (nombre, id_producto))
        if c.fetchone()[0] > 0:
            st.error(f"Ya existe otro producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
            return False
            
        c.execute("UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
                  (nombre, stock, precio, costo, id_producto))
        conn.commit()
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except sqlite3.Error as e:
        st.error(f"Error de base de datos al actualizar producto: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ------------------------------------------
# INTERFAZ DE USUARIO (Mantenemos las últimas versiones correctas)
# ------------------------------------------

def mostrar_inventario():
    """Muestra el inventario actual con auto-actualización"""
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos registrados.")
        return
    
    productos['Valor Total'] = productos['stock'] * productos['precio']
    productos['Costo Total'] = productos['stock'] * productos['costo']
    productos['Margen'] = productos['precio'] - productos['costo']
    productos['Margen %'] = (productos['Margen'] / productos['precio'] * 100).round(2)
    
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
    """Formulario para agregar nuevos productos"""
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
            elif precio <= 0 or costo < 0:
                st.error("Precio y costo deben ser valores positivos")
            else:
                if agregar_producto(nombre, stock, precio, costo):
                    st.success("¡Producto agregado correctamente!")
                    st.session_state.main_menu = "Ver Inventario"
                    st.experimental_rerun()

def mostrar_formulario_editar():
    """Formulario para editar productos existentes"""
    st.header("✏️ Editar Producto")
    
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos para editar")
        return

    producto_seleccionado_nombre = st.selectbox(
        "Seleccione un producto:",
        productos['nombre'],
        key="select_editar",
        index=0 if not productos.empty else None
    )
    
    if producto_seleccionado_nombre is None:
        return
        
    producto = productos[productos['nombre'] == producto_seleccionado_nombre].iloc[0]
    
    with st.form("form_editar"):
        nuevo_nombre = st.text_input("Nombre*", value=producto['nombre'], key="nombre_edit")
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input("Stock*", min_value=0, value=producto['stock'], key="stock_edit")
        nuevo_precio = col1.number_input("Precio*", min_value=0.0, value=producto['precio'], step=0.01, format="%.2f", key="precio_edit")
        nuevo_costo = col2.number_input("Costo*", min_value=0.0, value=producto['costo'], step=0.01, format="%.2f", key="costo_edit")
        
        if st.form_submit_button("Actualizar Producto"):
            if not nuevo_nombre:
                st.error("El nombre del producto es obligatorio")
            elif nuevo_precio <= 0 or nuevo_costo < 0:
                st.error("Precio y costo deben ser valores positivos")
            else:
                if actualizar_producto(producto['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
                    st.success("¡Producto actualizado correctamente!")
                    st.session_state.main_menu = "Ver Inventario"
                    st.experimental_rerun()

# ------------------------------------------
# MENÚ PRINCIPAL (REVISADO)
# ------------------------------------------

def main():
    # Inicializar la base de datos
    init_db()
    
    # Inicializar variables de estado si no existen
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
    # Inicializar la selección del menú si no existe
    # Esto DEBE hacerse antes de usar st.session_state.main_menu en st.radio
    if 'main_menu' not in st.session_state:
        st.session_state.main_menu = "Ver Inventario" # Valor predeterminado al iniciar la app

    menu_options = {
        "Ver Inventario": mostrar_inventario,
        "Agregar Producto": mostrar_formulario_agregar,
        "Editar Producto": mostrar_formulario_editar
    }
    
    with st.sidebar:
        st.title("Menú Principal")
        # Aquí asignamos el valor devuelto por st.radio a la variable de estado
        # El 'index' se calcula usando el valor actual de st.session_state.main_menu
        # Esto asegura que el widget se inicialice correctamente y que el estado sea consistente
        st.session_state.main_menu = st.radio(
            "Seleccione una opción:",
            list(menu_options.keys()),
            key="main_menu_radio", # Cambié la clave del widget para evitar posibles conflictos
            index=list(menu_options.keys()).index(st.session_state.main_menu)
        )
    
    # Ejecutar la función de la opción seleccionada
    menu_options[st.session_state.main_menu]()


if __name__ == "__main__":
    main()
