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
# FUNCIONES DE BASE DE DATOS
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
    """Obtiene todos los productos como DataFrame"""
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM productos ORDER BY nombre", conn)
        return df
    finally:
        conn.close()

# ------------------------------------------
# FUNCIONES PRINCIPALES CON ACTUALIZACIÓN DE ESTADO
# ------------------------------------------

def agregar_producto(nombre, stock, precio, costo):
    """Agrega un nuevo producto a la base de datos"""
    try:
        # Aquí puedes añadir la validación de nombre duplicado antes de ejecutar la consulta
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM productos WHERE nombre=?", (nombre,))
        if c.fetchone()[0] > 0:
            st.error(f"Ya existe un producto con el nombre '{nombre}'.")
            return False
        conn.close() # Cierra la conexión antes de abrir una nueva en ejecutar_consulta

        if ejecutar_consulta(
            "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
            (nombre, stock, precio, costo)
        ):
            st.session_state.ultima_actualizacion = datetime.now()
            return True
        return False
    except Exception as e:
        st.error(f"Error al agregar producto: {str(e)}")
        return False

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza los datos de un producto existente"""
    try:
        # Aquí también puedes añadir validación de nombre duplicado
        # PERO asegúrate de que no sea el mismo producto que se está editando
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM productos WHERE nombre=? AND id != ?", (nombre, id_producto))
        if c.fetchone()[0] > 0:
            st.error(f"Ya existe otro producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
            return False
        conn.close()

        if ejecutar_consulta(
            "UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
            (nombre, stock, precio, costo, id_producto)
        ):
            st.session_state.ultima_actualizacion = datetime.now()
            return True
        return False
    except Exception as e:
        st.error(f"Error al actualizar producto: {str(e)}")
        return False

# ------------------------------------------
# INTERFAZ DE USUARIO CON ACTUALIZACIÓN AUTOMÁTICA
# ------------------------------------------

def mostrar_inventario():
    """Muestra el inventario actual con auto-actualización"""
    # Usamos un marcador de tiempo para forzar la actualización
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
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
    """Formulario para agregar nuevos productos"""
    st.header("➕ Agregar Nuevo Producto")
    
    # Esta función ahora devuelve True si la operación fue exitosa y False si no
    action_successful = False

    with st.form("form_agregar", clear_on_submit=True):
        nombre = st.text_input("Nombre del Producto*")
        col1, col2 = st.columns(2)
        stock = col1.number_input("Stock Inicial*", min_value=0, value=0)
        precio = col1.number_input("Precio de Venta*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        costo = col2.number_input("Costo del Producto*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        if st.form_submit_button("Agregar Producto"):
            if not nombre:
                st.error("El nombre del producto es obligatorio")
                return False # No exitoso
                
            if precio <= 0 or costo < 0:
                st.error("Precio y costo deben ser valores positivos")
                return False # No exitoso
                
            if agregar_producto(nombre, stock, precio, costo):
                st.success("¡Producto agregado correctamente!")
                st.session_state.ultima_actualizacion = datetime.now()
                action_successful = True
            else:
                action_successful = False # Falló agregar_producto
    return action_successful

def mostrar_formulario_editar():
    """Formulario para editar productos existentes"""
    st.header("✏️ Editar Producto")
    
    # Esta función ahora devuelve True si la operación fue exitosa y False si no
    action_successful = False

    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos para editar")
        return False
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        productos['nombre'],
        key="select_editar"
    )
    
    # Si no hay un producto seleccionado (ej. la lista acaba de vaciarse), sal
    if producto_seleccionado is None:
        return False
        
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
                return False # No exitoso
                
            if nuevo_precio <= 0 or nuevo_costo < 0:
                st.error("Precio y costo deben ser valores positivos")
                return False # No exitoso
                
            if actualizar_producto(producto['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
                st.success("¡Producto actualizado correctamente!")
                st.session_state.ultima_actualizacion = datetime.now()
                action_successful = True
            else:
                action_successful = False # Falló actualizar_producto
    return action_successful

# ------------------------------------------
# MENÚ PRINCIPAL
# ------------------------------------------

def main():
    # Inicializar la base de datos
    init_db()
    
    # Inicializar variable de estado si no existe
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
    # Inicializar la bandera de rerun
    if 'do_rerun' not in st.session_state:
        st.session_state.do_rerun = False

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
    
    # Ejecutar la función de la opción seleccionada
    # IMPORTANTE: Captura el resultado si la función indica que se realizó una acción de modificación
    action_performed = False
    if selected == "Agregar Producto":
        action_performed = mostrar_formulario_agregar()
    elif selected == "Editar Producto":
        action_performed = mostrar_formulario_editar()
    else:
        # Para "Ver Inventario", simplemente llama a la función
        menu_options[selected]()
    
    # Si alguna de las funciones de acción indicó que se realizó una operación exitosa,
    # establece la bandera para el rerun.
    if action_performed:
        st.session_state.do_rerun = True

    # Realiza el rerun **solo si la bandera está activada**
    if st.session_state.do_rerun:
        st.session_state.do_rerun = False # Resetear la bandera para evitar bucles infinitos
        st.experimental_rerun()


if __name__ == "__main__":
    main()
