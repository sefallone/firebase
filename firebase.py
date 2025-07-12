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
    conn = None
    try:
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
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER,
                tipo TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                nota TEXT,
                FOREIGN KEY (producto_id) REFERENCES productos (id)
            )
        ''')
        
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Error al inicializar la base de datos: {str(e)}")
    finally:
        if conn:
            conn.close()

def get_connection():
    """Obtiene una conexión a la base de datos con reintentos"""
    try:
        return sqlite3.connect(DB_FILE)
    except sqlite3.Error as e:
        st.error(f"Error de conexión: {str(e)}")
        return None

def obtener_productos():
    """Obtiene todos los productos con manejo de errores"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        df = pd.read_sql("SELECT * FROM productos ORDER BY nombre", conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Error al obtener productos: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

def ejecutar_consulta(query, params=()):
    """Ejecuta una consulta SQL con manejo de transacciones"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        st.error(f"Error en consulta: {str(e)}")
        return False
    finally:
        conn.close()

# ------------------------------------------
# FUNCIONES PRINCIPALES CON PERSISTENCIA
# ------------------------------------------

def agregar_producto(nombre, stock, precio, costo):
    """Agrega un producto con persistencia garantizada"""
    # Validación de datos
    if not nombre or precio <= 0 or costo < 0 or stock < 0:
        return False
    
    # Insertar producto
    if not ejecutar_consulta(
        "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
        (nombre, stock, precio, costo)
    ):
        return False
    
    # Registrar movimiento inicial
    producto_id = ejecutar_consulta("SELECT last_insert_rowid()", fetch=True)
    if producto_id:
        ejecutar_consulta(
            "INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?, ?, ?, ?)",
            (producto_id[0][0], 'entrada', stock, 'Stock inicial')
        )
    
    return True

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza un producto con validación"""
    if not nombre or precio <= 0 or costo < 0 or stock < 0:
        return False
    
    return ejecutar_consulta(
        "UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
        (nombre, stock, precio, costo, id_producto)
    )

def eliminar_producto(id_producto):
    """Elimina un producto con transacción"""
    return ejecutar_consulta("DELETE FROM productos WHERE id=?", (id_producto,))

def ajustar_stock(id_producto, cantidad, tipo='salida', nota=""):
    """Ajusta el stock con operación atómica"""
    operador = '+' if tipo == 'entrada' else '-'
    
    if not ejecutar_consulta(
        f"UPDATE productos SET stock = stock {operador} ? WHERE id=?",
        (cantidad, id_producto)
    ):
        return False
    
    return ejecutar_consulta(
        "INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?, ?, ?, ?)",
        (id_producto, tipo, cantidad, nota)
    )

# ------------------------------------------
# INTERFAZ DE USUARIO CON ACTUALIZACIÓN
# ------------------------------------------

def mostrar_inventario():
    """Muestra el inventario actual con auto-actualización"""
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos registrados.")
        return
    
    # Cálculos adicionales
    productos['Valor Total'] = productos['stock'] * productos['precio']
    productos['Costo Total'] = productos['stock'] * productos['costo']
    productos['Margen'] = productos['precio'] - productos['costo']
    productos['Margen %'] = (productos['Margen'] / productos['precio'] * 100).round(2)
    
    # Mostrar tabla
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
    
    with st.form("form_agregar"):
        nombre = st.text_input("Nombre del Producto*")
        col1, col2 = st.columns(2)
        stock = col1.number_input("Stock Inicial*", min_value=0, value=0)
        precio = col1.number_input("Precio de Venta*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        costo = col2.number_input("Costo del Producto*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        if st.form_submit_button("Agregar"):
            if not nombre:
                st.error("Nombre es obligatorio")
                return
                
            if agregar_producto(nombre, stock, precio, costo):
                st.success("¡Producto agregado!")
                st.session_state.ultima_actualizacion = datetime.now()
            else:
                st.error("Error al agregar producto")

def mostrar_formulario_editar():
    """Formulario para editar productos"""
    st.header("✏️ Editar Producto")
    
    productos = obtener_productos()
    if productos.empty:
        st.warning("No hay productos para editar")
        return
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        productos['nombre']
    )
    
    producto = productos[productos['nombre'] == producto_seleccionado].iloc[0]
    
    with st.form("form_editar"):
        nuevo_nombre = st.text_input("Nombre*", value=producto['nombre'])
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input("Stock*", min_value=0, value=producto['stock'])
        nuevo_precio = col1.number_input("Precio*", min_value=0.0, value=producto['precio'], step=0.01, format="%.2f")
        nuevo_costo = col2.number_input("Costo*", min_value=0.0, value=producto['costo'], step=0.01, format="%.2f")
        
        if st.form_submit_button("Actualizar"):
            if actualizar_producto(producto['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
                st.success("¡Producto actualizado!")
                st.session_state.ultima_actualizacion = datetime.now()
            else:
                st.error("Error al actualizar")

def mostrar_formulario_eliminar():
    """Formulario para eliminar productos"""
    st.header("🗑️ Eliminar Producto")
    
    productos = obtener_productos()
    if productos.empty:
        st.warning("No hay productos para eliminar")
        return
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        productos['nombre']
    )
    
    producto = productos[productos['nombre'] == producto_seleccionado].iloc[0]
    
    st.warning(f"¿Eliminar {producto['nombre']} permanentemente?")
    
    if st.button("Confirmar Eliminación"):
        if eliminar_producto(producto['id']):
            st.success("¡Producto eliminado!")
            st.session_state.ultima_actualizacion = datetime.now()
        else:
            st.error("Error al eliminar")

def mostrar_formulario_ajuste_stock():
    """Formulario para ajustar stock"""
    st.header("🔄 Ajustar Stock")
    
    productos = obtener_productos()
    if productos.empty:
        st.warning("No hay productos disponibles")
        return
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        productos['nombre']
    )
    
    producto = productos[productos['nombre'] == producto_seleccionado].iloc[0]
    
    st.info(f"Stock actual: {producto['stock']}")
    
    tipo_ajuste = st.radio(
        "Tipo de ajuste:",
        ["Entrada (+)", "Salida (-)"],
        horizontal=True
    )
    
    cantidad = st.number_input(
        "Cantidad*",
        min_value=1,
        max_value=10000 if tipo_ajuste == "Entrada (+)" else producto['stock'],
        value=1
    )
    
    if st.button("Aplicar Ajuste"):
        tipo = 'entrada' if tipo_ajuste == "Entrada (+)" else 'salida'
        if ajustar_stock(producto['id'], cantidad, tipo):
            st.success(f"¡Stock actualizado! ({tipo_ajuste} de {cantidad} unidades)")
            st.session_state.ultima_actualizacion = datetime.now()
        else:
            st.error("Error al ajustar stock")

# ------------------------------------------
# CONFIGURACIÓN PRINCIPAL
# ------------------------------------------

def main():
    # Inicializar base de datos
    init_db()
    
    # Inicializar estado si no existe
    if 'ultima_actualizacion' not in st.session_state:
        st.session_state.ultima_actualizacion = datetime.now()
    
    # Menú de opciones
    menu_options = {
        "Ver Inventario": mostrar_inventario,
        "Agregar Producto": mostrar_formulario_agregar,
        "Editar Producto": mostrar_formulario_editar,
        "Eliminar Producto": mostrar_formulario_eliminar,
        "Ajustar Stock": mostrar_formulario_ajuste_stock
    }
    
    with st.sidebar:
        st.title("Menú Principal")
        selected = st.radio(
            "Seleccione una opción:",
            list(menu_options.keys())
        )
    
    # Mostrar la opción seleccionada
    menu_options[selected]()

if __name__ == "__main__":
    main()
