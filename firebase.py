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

# Esta función se mantiene para consultas simples o inicialización
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

# ------------------------------------------
# FUNCIONES PRINCIPALES CON ACTUALIZACIÓN DE ESTADO
# ------------------------------------------

def agregar_producto(nombre, stock, precio, costo):
    """Agrega un nuevo producto a la base de datos, con verificación de duplicados."""
    conn = get_connection() # Obtener la conexión una sola vez
    try:
        c = conn.cursor()
        
        # 1. Verificar si el nombre ya existe
        c.execute("SELECT COUNT(*) FROM productos WHERE nombre=?", (nombre,))
        if c.fetchone()[0] > 0:
            st.error(f"Ya existe un producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
            return False # No continuar si es duplicado
            
        # 2. Si no es duplicado, proceder con la inserción
        c.execute("INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
                  (nombre, stock, precio, costo))
        conn.commit() # Confirmar la transacción
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except sqlite3.Error as e:
        st.error(f"Error de base de datos al agregar producto: {str(e)}")
        conn.rollback() # Revertir la transacción en caso de error
        return False
    finally:
        conn.close() # Asegurarse de cerrar la conexión

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza los datos de un producto existente, con verificación de duplicados."""
    conn = get_connection() # Obtener la conexión una sola vez
    try:
        c = conn.cursor()
        
        # 1. Verificar si el nuevo nombre ya existe en OTRO producto
        # Se excluye el ID del producto que se está editando para permitir que conserve su propio nombre.
        c.execute("SELECT COUNT(*) FROM productos WHERE nombre=? AND id != ?", (nombre, id_producto))
        if c.fetchone()[0] > 0:
            st.error(f"Ya existe otro producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
            return False # No continuar si es duplicado
            
        # 2. Si el nombre es único (o es el mismo nombre del producto que se edita), proceder con la actualización
        c.execute("UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
                  (nombre, stock, precio, costo, id_producto))
        conn.commit() # Confirmar la transacción
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except sqlite3.Error as e:
        st.error(f"Error de base de datos al actualizar producto: {str(e)}")
        conn.rollback() # Revertir la transacción en caso de error
        return False
    finally:
        conn.close() # Asegurarse de cerrar la conexión

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
                    # Redirigir a "Ver Inventario" y forzar un rerun para ver los cambios
                    st.session_state.main_menu = "Ver Inventario"
                    st.experimental_rerun()
                # Si agregar_producto falla (ej. duplicado), ya muestra el st.error.
                # No se necesita un rerun en caso de fallo, el usuario permanece en el formulario.

def mostrar_formulario_editar():
    """Formulario para editar productos existentes"""
    st.header("✏️ Editar Producto")
    
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos para editar")
        return # No hay productos, no hay nada que seleccionar

    # Asegúrate de que el selectbox se inicializa con un valor si hay productos
    producto_seleccionado_nombre = st.selectbox(
        "Seleccione un producto:",
        productos['nombre'],
        key="select_editar",
        # Si la lista no está vacía, selecciona el primer elemento por defecto
        index=0 if not productos.empty else None
    )
    
    # Si por alguna razón no se seleccionó nada (ej. lista se vació justo ahora), sal
    if producto_seleccionado_nombre is None:
        return
        
    # Obtener el producto completo basado en el nombre seleccionado
    producto = productos[productos['nombre'] == producto_seleccionado_nombre].iloc[0]
    
    with st.form("form_editar"):
        # Asegúrate de que los valores iniciales se toman del producto seleccionado
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
                # Pasa el ID del producto para la actualización
                if actualizar_producto(producto['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
                    st.success("¡Producto actualizado correctamente!")
                    # Redirigir a "Ver Inventario" y forzar un rerun para ver los cambios
                    st.session_state.main_menu = "Ver Inventario"
                    st.experimental_rerun()
                # Si actualizar_producto falla (ej. duplicado), ya muestra el st.error.
                # No se necesita un rerun en caso de fallo, el usuario permanece en el formulario.

# ------------------------------------------
# MENÚ PRINCIPAL
# ------------------------------------------

def main():
    # Inicializar la base de datos
    init_db()
    
    # Inicializar variables de estado si no existen
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
    # Inicializar la selección del menú si no existe, o si es la primera vez que se carga
    if 'main_menu' not in st.session_state:
        st.session_state.main_menu = "Ver Inventario"

    menu_options = {
        "Ver Inventario": mostrar_inventario,
        "Agregar Producto": mostrar_formulario_agregar,
        "Editar Producto": mostrar_formulario_editar
    }
    
    with st.sidebar:
        st.title("Menú Principal")
        # El st.radio ahora se enlaza directamente a st.session_state.main_menu
        st.session_state.main_menu = st.radio(
            "Seleccione una opción:",
            list(menu_options.keys()),
            key="main_menu", # Usamos la misma clave para que el widget y el estado estén sincronizados
            index=list(menu_options.keys()).index(st.session_state.main_menu)
        )
    
    # Ejecutar la función de la opción seleccionada
    # Ya no necesitamos el `action_performed` flag aquí,
    # el rerun se maneja dentro de las funciones de formulario.
    menu_options[st.session_state.main_menu]()


if __name__ == "__main__":
    main()
