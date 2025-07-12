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
# FUNCIONES MEJORADAS DE BASE DE DATOS
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

def obtener_productos(refresh=False):
    """Obtiene productos con opción de forzar actualización"""
    if not refresh and 'productos_df' in st.session_state:
        return st.session_state.productos_df
    
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM productos ORDER BY nombre", conn)
        st.session_state.productos_df = df  # Cache en session_state
        return df
    finally:
        conn.close()

# ------------------------------------------
# FUNCIONES PRINCIPALES MEJORADAS
# ------------------------------------------

def agregar_producto(nombre, stock, precio, costo):
    """Agrega un nuevo producto con actualización de estado"""
    if ejecutar_consulta(
        "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
        (nombre, stock, precio, costo)
    ):
        # Registrar movimiento inicial
        producto_id = ejecutar_consulta("SELECT last_insert_rowid()", fetch=True)[0][0]
        ejecutar_consulta(
            "INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?, ?, ?, ?)",
            (producto_id, 'entrada', stock, 'Stock inicial')
        )
        st.session_state.productos_df = obtener_productos(refresh=True)  # Forzar actualización
        return True
    return False

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza un producto con manejo de estado"""
    if ejecutar_consulta(
        "UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
        (nombre, stock, precio, costo, id_producto)
    ):
        st.session_state.productos_df = obtener_productos(refresh=True)
        return True
    return False

def eliminar_producto(id_producto):
    """Elimina un producto con actualización de estado"""
    if ejecutar_consulta("DELETE FROM productos WHERE id=?", (id_producto,)):
        st.session_state.productos_df = obtener_productos(refresh=True)
        return True
    return False

def ajustar_stock(id_producto, cantidad, tipo='salida', nota=""):
    """Ajusta el stock con actualización de estado"""
    operador = '+' if tipo == 'entrada' else '-'
    if ejecutar_consulta(
        f"UPDATE productos SET stock = stock {operador} ? WHERE id=?",
        (cantidad, id_producto)
    ):
        ejecutar_consulta(
            "INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?, ?, ?, ?)",
            (id_producto, tipo, cantidad, nota)
        )
        st.session_state.productos_df = obtener_productos(refresh=True)
        return True
    return False

# ------------------------------------------
# INTERFAZ DE USUARIO MEJORADA
# ------------------------------------------

def mostrar_inventario():
    st.header("📋 Inventario Actual")
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
            'precio': '${:,.2f}', 'costo': '${:,.2f}',
            'Valor Total': '${:,.2f}', 'Costo Total': '${:,.2f}',
            'Margen': '${:,.2f}', 'Margen %': '{:.2f}%'
        }),
        use_container_width=True
    )

def formulario_editar_producto():
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
        nuevo_nombre = st.text_input("Nombre", value=producto['nombre'])
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input("Stock", min_value=0, value=producto['stock'])
        nuevo_precio = col1.number_input("Precio", min_value=0.0, value=producto['precio'], step=0.01, format="%.2f")
        nuevo_costo = col2.number_input("Costo", min_value=0.0, value=producto['costo'], step=0.01, format="%.2f")
        
        if st.form_submit_button("Actualizar Producto"):
            if actualizar_producto(producto['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
                st.success("¡Producto actualizado!")
                st.rerun()

def formulario_eliminar_producto():
    st.header("🗑️ Eliminar Producto")
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos para eliminar")
        return
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        productos['nombre'],
        key="select_eliminar"
    )
    
    producto = productos[productos['nombre'] == producto_seleccionado].iloc[0]
    
    st.warning(f"¿Está seguro que desea eliminar '{producto['nombre']}'?")
    st.write(f"Stock actual: {producto['stock']} | Precio: ${producto['precio']:.2f}")
    
    if st.button("Confirmar Eliminación", key="btn_eliminar"):
        if eliminar_producto(producto['id']):
            st.success("¡Producto eliminado!")
            st.rerun()

def formulario_ajustar_stock():
    st.header("🔄 Ajustar Stock")
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos disponibles")
        return
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        productos['nombre'],
        key="select_ajustar"
    )
    
    producto = productos[productos['nombre'] == producto_seleccionado].iloc[0]
    
    st.info(f"Stock actual: {producto['stock']}")
    
    tipo_ajuste = st.radio(
        "Tipo de ajuste:",
        ['Entrada (+)', 'Salida (-)'],
        key="radio_ajuste"
    )
    
    cantidad = st.number_input(
        "Cantidad",
        min_value=1,
        max_value=10000 if tipo_ajuste == 'Entrada (+)' else producto['stock'],
        value=1,
        key="num_ajuste"
    )
    
    nota = st.text_input("Nota (opcional)", key="nota_ajuste")
    
    if st.button("Aplicar Ajuste", key="btn_ajuste"):
        tipo = 'entrada' if tipo_ajuste == 'Entrada (+)' else 'salida'
        if ajustar_stock(producto['id'], cantidad, tipo, nota):
            st.success(f"¡Stock actualizado! ({tipo_ajuste} de {cantidad} unidades)")
            st.rerun()

# ------------------------------------------
# EJECUCIÓN PRINCIPAL
# ------------------------------------------

def main():
    init_db()  # Asegurar que la base de datos existe
    
    menu_options = {
        "Ver Inventario": mostrar_inventario,
        "Agregar Producto": formulario_agregar_producto,
        "Editar Producto": formulario_editar_producto,
        "Eliminar Producto": formulario_eliminar_producto,
        "Ajustar Stock": formulario_ajustar_stock
    }
    
    with st.sidebar:
        st.title("Menú Principal")
        selected = st.radio("Opciones:", list(menu_options.keys()))
    
    menu_options[selected]()

if __name__ == "__main__":
    main()
