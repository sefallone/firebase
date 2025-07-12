import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os

# Configuración de la página
st.set_page_config(page_title="Sistema de Inventario", layout="wide")
st.title("📦 Sistema de Gestión de Inventario")

# Configuración de la base de datos
DB_FILE = "inventario.db"

def init_db():
    """Inicializa la base de datos si no existe"""
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
            tipo TEXT NOT NULL,  -- 'entrada' o 'salida'
            cantidad INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_connection():
    """Obtiene una conexión a la base de datos"""
    return sqlite3.connect(DB_FILE)

# Inicializar la base de datos
init_db()

# Funciones principales
def agregar_producto(nombre, stock, precio, costo):
    """Agrega un nuevo producto a la base de datos"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
            (nombre, stock, precio, costo)
        )
        # Registrar movimiento inicial
        producto_id = c.lastrowid
        c.execute(
            "INSERT INTO movimientos (producto_id, tipo, cantidad) VALUES (?, ?, ?)",
            (producto_id, 'entrada', stock)
        )
        conn.commit()
        st.success(f"Producto '{nombre}' agregado correctamente!")
    except sqlite3.IntegrityError:
        st.error(f"Error: Ya existe un producto con el nombre '{nombre}'")
    except Exception as e:
        st.error(f"Error al agregar producto: {str(e)}")
    finally:
        conn.close()

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza los datos de un producto existente"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "UPDATE productos SET nombre=?, stock=?, precio=?, costo=? WHERE id=?",
            (nombre, stock, precio, costo, id_producto)
        )
        conn.commit()
        st.success("Producto actualizado correctamente!")
    except Exception as e:
        st.error(f"Error al actualizar producto: {str(e)}")
    finally:
        conn.close()

def eliminar_producto(id_producto):
    """Elimina un producto de la base de datos"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM productos WHERE id=?", (id_producto,))
        conn.commit()
        st.success("Producto eliminado correctamente!")
    except Exception as e:
        st.error(f"Error al eliminar producto: {str(e)}")
    finally:
        conn.close()

def ajustar_stock(id_producto, cantidad, tipo='salida'):
    """Ajusta el stock de un producto (entrada o salida)"""
    try:
        conn = get_connection()
        c = conn.cursor()
        
        # Actualizar stock
        if tipo == 'entrada':
            c.execute(
                "UPDATE productos SET stock = stock + ? WHERE id=?",
                (cantidad, id_producto)
            )
        else:  # salida
            c.execute(
                "UPDATE productos SET stock = stock - ? WHERE id=?",
                (cantidad, id_producto)
            )
        
        # Registrar movimiento
        c.execute(
            "INSERT INTO movimientos (producto_id, tipo, cantidad) VALUES (?, ?, ?)",
            (id_producto, tipo, cantidad)
        )
        
        conn.commit()
        st.success(f"Stock actualizado correctamente ({tipo} de {cantidad} unidades)")
    except Exception as e:
        st.error(f"Error al ajustar stock: {str(e)}")
    finally:
        conn.close()

def obtener_productos():
    """Obtiene todos los productos como DataFrame"""
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM productos ORDER BY nombre", conn)
    conn.close()
    return df

def obtener_movimientos():
    """Obtiene el historial de movimientos"""
    conn = get_connection()
    df = pd.read_sql('''
        SELECT m.fecha, p.nombre, m.tipo, m.cantidad, p.precio 
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        ORDER BY m.fecha DESC
    ''', conn)
    conn.close()
    return df

# Interfaz de usuario
def mostrar_inventario():
    st.header("Inventario Actual")
    productos = obtener_productos()
    
    if productos.empty:
        st.warning("No hay productos registrados.")
        return
    
    # Calcular valores adicionales
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
    
    # Resumen
    st.subheader("Resumen del Inventario")
    cols = st.columns(4)
    cols[0].metric("Total Productos", len(productos))
    cols[1].metric("Valor Total", f"${productos['Valor Total'].sum():,.2f}")
    cols[2].metric("Costo Total", f"${productos['Costo Total'].sum():,.2f}")
    cols[3].metric("Margen Promedio", f"{productos['Margen %'].mean():.2f}%")

def formulario_agregar_producto():
    st.header("Agregar Nuevo Producto")
    nombre = st.text_input("Nombre del Producto*", key="nombre_input")
    col1, col2 = st.columns(2)
    stock = col1.number_input("Stock Inicial*", min_value=0, value=0, key="stock_input")
    precio = col1.number_input("Precio de Venta*", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="precio_input")
    costo = col2.number_input("Costo del Producto*", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="costo_input")
    
    if st.button("Agregar Producto", key="agregar_btn"):
        if nombre and precio > 0 and costo >= 0:
            agregar_producto(nombre, stock, precio, costo)
            st.success("¡Producto agregado!") 
            # No se necesita rerun si usamos keys únicos
        else:
            st.error("Complete todos los campos obligatorios (*)")

def formulario_editar_producto():
    st.header("Editar Producto")
    
    if 'productos' not in st.session_state:
        st.session_state.productos = obtener_productos()
    
    if st.session_state.productos.empty:
        st.warning("No hay productos para editar")
        return
    
    producto_seleccionado = st.selectbox(
        "Seleccione un producto:",
        st.session_state.productos['nombre'],
        key="select_editar_alt"
    )
    
    producto = st.session_state.productos[
        st.session_state.productos['nombre'] == producto_seleccionado
    ].iloc[0]
    
    with st.form("form_editar_alt"):
        nuevo_nombre = st.text_input("Nombre", value=producto['nombre'])
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input("Stock", min_value=0, value=producto['stock'])
        nuevo_precio = col1.number_input("Precio", min_value=0.0, value=producto['precio'], step=0.01, format="%.2f")
        nuevo_costo = col2.number_input("Costo", min_value=0.0, value=producto['costo'], step=0.01, format="%.2f")
        
        if st.form_submit_button("Actualizar Producto"):
            if nuevo_nombre and nuevo_precio > 0 and nuevo_costo >= 0:
                actualizar_producto(
                    producto['id'],
                    nuevo_nombre,
                    nuevo_stock,
                    nuevo_precio,
                    nuevo_costo
                )
                st.success("¡Producto actualizado!")
                st.session_state.productos = obtener_productos()  # Actualiza los datos
            else:
                st.error("Complete todos los campos obligatorios")

def formulario_eliminar_producto():
    st.header("Eliminar Producto")
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
    
    st.warning(f"¿Está seguro que desea eliminar permanentemente este producto?")
    st.json({
        "Nombre": producto['nombre'],
        "Stock actual": producto['stock'],
        "Precio": f"${producto['precio']:,.2f}",
        "Costo": f"${producto['costo']:,.2f}"
    })
    
    if st.button("Confirmar Eliminación"):
        eliminar_producto(producto['id'])
        st.experimental_rerun()


def formulario_ajustar_stock():
    st.header("Ajustar Stock")
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
        ['Entrada (aumentar stock)', 'Salida (reducir stock)'],
        key="radio_ajuste"
    )
    
    cantidad = st.number_input(
        "Cantidad",
        min_value=1,
        max_value=10000 if tipo_ajuste.startswith('Entrada') else producto['stock'],
        value=1
    )
    
    if st.button("Aplicar Ajuste"):
        ajustar_stock(
            producto['id'],
            cantidad,
            'entrada' if tipo_ajuste.startswith('Entrada') else 'salida'
        )
        st.experimental_rerun()

def mostrar_historial():
    st.header("Historial de Movimientos")
    movimientos = obtener_movimientos()
    
    if movimientos.empty:
        st.warning("No hay movimientos registrados")
        return
    
    movimientos['Valor'] = movimientos['cantidad'] * movimientos['precio']
    st.dataframe(
        movimientos.style.format({
            'precio': '${:,.2f}',
            'Valor': '${:,.2f}'
        }),
        use_container_width=True
    )

# Menú principal
menu = {
    "Ver Inventario": mostrar_inventario,
    "Agregar Producto": formulario_agregar_producto,
    "Editar Producto": formulario_editar_producto,
    "Eliminar Producto": formulario_eliminar_producto,
    "Ajustar Stock": formulario_ajustar_stock,
    "Historial": mostrar_historial
}

with st.sidebar:
    st.header("Menú Principal")
    opcion = st.radio(
        "Seleccione una opción:",
        list(menu.keys())
    )

# Mostrar la opción seleccionada
menu[opcion]()
