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
    
    # Tabla de productos
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
    
    # Tabla de movimientos (historial)
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

def ejecutar_consulta(query, params=(), fetch=False):
    """Ejecuta una consulta SQL con manejo de errores mejorado"""
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        if fetch:
            if query.strip().upper().startswith("SELECT"):
                return c.fetchall()
            return None
        return True
    except sqlite3.Error as e:
        st.error(f"Error de base de datos: {str(e)}")
        return False
    finally:
        conn.close()

def obtener_productos():
    """Obtiene todos los productos actualizados"""
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
    """Agrega un nuevo producto con actualización de estado"""
    try:
        # Insertar producto
        if not ejecutar_consulta(
            "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
            (nombre, stock, precio, costo)
        ):
            return False
        
        # Obtener ID del producto insertado
        producto_id = ejecutar_consulta("SELECT last_insert_rowid()", fetch=True)[0][0]
        
        # Registrar movimiento inicial
        ejecutar_consulta(
            "INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?, ?, ?, ?)",
            (producto_id, 'entrada', stock, 'Stock inicial')
        )
        
        # Forzar actualización del estado
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except Exception as e:
        st.error(f"Error al agregar producto: {str(e)}")
        return False

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza un producto con manejo de estado"""
    try:
        if not ejecutar_consulta(
            "UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
            (nombre, stock, precio, costo, id_producto)
        ):
            return False
        
        # Forzar actualización del estado
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except Exception as e:
        st.error(f"Error al actualizar producto: {str(e)}")
        return False

def eliminar_producto(id_producto):
    """Elimina un producto con actualización de estado"""
    try:
        if not ejecutar_consulta("DELETE FROM productos WHERE id=?", (id_producto,)):
            return False
        
        # Forzar actualización del estado
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except Exception as e:
        st.error(f"Error al eliminar producto: {str(e)}")
        return False

def ajustar_stock(id_producto, cantidad, tipo='salida', nota=""):
    """Ajusta el stock con actualización de estado"""
    try:
        operador = '+' if tipo == 'entrada' else '-'
        
        if not ejecutar_consulta(
            f"UPDATE productos SET stock = stock {operador} ? WHERE id=?",
            (cantidad, id_producto)
        ):
            return False
        
        # Registrar movimiento
        ejecutar_consulta(
            "INSERT INTO movimientos (producto_id, tipo, cantidad, nota) VALUES (?, ?, ?, ?)",
            (id_producto, tipo, cantidad, nota)
        )
        
        # Forzar actualización del estado
        st.session_state.ultima_actualizacion = datetime.now()
        return True
    except Exception as e:
        st.error(f"Error al ajustar stock: {str(e)}")
        return False

# ------------------------------------------
# INTERFAZ DE USUARIO CON ACTUALIZACIÓN AUTOMÁTICA
# ------------------------------------------

def mostrar_inventario():
    """Muestra el inventario actual con auto-actualización"""
    # Verificar si necesitamos actualizar
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
        })),
    use_container_width=True,
    height=min(400, 35 + 35 * len(productos))
    
    # Resumen estadístico
    st.subheader("📊 Resumen del Inventario")
    cols = st.columns(4)
    cols[0].metric("Total Productos", len(productos))
    cols[1].metric("Valor Total", f"${productos['Valor Total'].sum():,.2f}")
    cols[2].metric("Costo Total", f"${productos['Costo Total'].sum():,.2f}")
    cols[3].metric("Margen Promedio", f"{productos['Margen %'].mean():.2f}%")

def mostrar_formulario_agregar():
    """Formulario para agregar productos con auto-actualización"""
    st.header("➕ Agregar Nuevo Producto")
    
    with st.form("form_agregar", clear_on_submit=True):
        nombre = st.text_input("Nombre del Producto*")
        col1, col2 = st.columns(2)
        stock = col1.number_input("Stock Inicial*", min_value=0, value=0)
        precio = col1.number_input("Precio de Venta*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        costo = col2.number_input("Costo del Producto*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        submitted = st.form_submit_button("Agregar Producto")
        
        if submitted:
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
    """Formulario para editar productos con auto-actualización"""
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
        nuevo_nombre = st.text_input("Nombre*", value=producto['nombre'])
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input("Stock*", min_value=0, value=producto['stock'])
        nuevo_precio = col1.number_input("Precio*", min_value=0.0, value=producto['precio'], step=0.01, format="%.2f")
        nuevo_costo = col2.number_input("Costo*", min_value=0.0, value=producto['costo'], step=0.01, format="%.2f")
        
        submitted = st.form_submit_button("Actualizar Producto")
        
        if submitted:
            if not nuevo_nombre:
                st.error("El nombre del producto es obligatorio")
                return
                
            if nuevo_precio <= 0 or nuevo_costo < 0:
                st.error("Precio y costo deben ser valores positivos")
                return
                
            if actualizar_producto(producto['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
                st.success("¡Producto actualizado correctamente!")
                st.experimental_rerun()

def mostrar_formulario_eliminar():
    """Formulario para eliminar productos con auto-actualización"""
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
    
    st.warning("⚠️ ¿Está seguro que desea eliminar este producto permanentemente?")
    
    with st.expander("Detalles del producto"):
        st.write(f"**Nombre:** {producto['nombre']}")
        st.write(f"**Stock actual:** {producto['stock']}")
        st.write(f"**Precio:** ${producto['precio']:.2f}")
        st.write(f"**Costo:** ${producto['costo']:.2f}")
    
    if st.button("Confirmar Eliminación", type="primary", key="btn_eliminar"):
        if eliminar_producto(producto['id']):
            st.success("¡Producto eliminado correctamente!")
            st.experimental_rerun()

def mostrar_formulario_ajuste_stock():
    """Formulario para ajustar stock con auto-actualización"""
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
    
    st.info(f"**Stock actual:** {producto['stock']} unidades")
    
    tipo_ajuste = st.radio(
        "Tipo de ajuste:",
        ["Entrada (+)", "Salida (-)"],
        key="radio_ajuste",
        horizontal=True
    )
    
    cantidad = st.number_input(
        "Cantidad*",
        min_value=1,
        max_value=10000 if tipo_ajuste == "Entrada (+)" else producto['stock'],
        value=1,
        key="num_ajuste"
    )
    
    nota = st.text_input("Nota (opcional)", key="nota_ajuste")
    
    if st.button("Aplicar Ajuste", type="primary", key="btn_ajuste"):
        tipo = 'entrada' if tipo_ajuste == "Entrada (+)" else 'salida'
        if ajustar_stock(producto['id'], cantidad, tipo, nota):
            st.success(f"¡Stock actualizado! ({tipo_ajuste} de {cantidad} unidades)")
            st.experimental_rerun()

# ------------------------------------------
# CONFIGURACIÓN DEL MENÚ PRINCIPAL
# ------------------------------------------

def main():
    # Inicializar la base de datos
    init_db()
    
    # Configurar el menú de opciones
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
            list(menu_options.keys()),
            key="main_menu"
        )
    
    # Mostrar la opción seleccionada
    menu_options[selected]()

if __name__ == "__main__":
    main()
