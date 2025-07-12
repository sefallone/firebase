import streamlit as st
import pandas as pd
import sqlite3
import os

# Configuración de la página
st.set_page_config(page_title="Sistema de Inventario", layout="wide")

# Título de la aplicación
st.title("📦 Sistema de Gestión de Inventario Local")

# Conexión con SQLite
DB_FILE = "inventario.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            stock INTEGER,
            precio REAL,
            costo REAL
        )
    ''')
    conn.commit()
    conn.close()

def load_inventario():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql('SELECT nombre, stock, precio, costo FROM inventario', conn)
    conn.close()
    return df

def save_producto(nombre, stock, precio, costo):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO inventario (nombre, stock, precio, costo)
        VALUES (?, ?, ?, ?)
    ''', (nombre, stock, precio, costo))
    conn.commit()
    conn.close()

# [Resto de las funciones y la interfaz...]
def agregar_producto(nombre, stock, precio, costo):
    try:
        nuevo_producto = pd.DataFrame([[nombre, stock, precio, costo]], 
                                    columns=['Nombre del Producto', 'Stock', 'Precio', 'Costo'])
        st.session_state.inventario = pd.concat([st.session_state.inventario, nuevo_producto], ignore_index=True)
        save_inventario(sheet, st.session_state.inventario)
        st.success(f"Producto '{nombre}' agregado correctamente!")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Error al agregar producto: {e}")

# Función para eliminar un producto
def eliminar_producto(nombre):
    try:
        if nombre in st.session_state.inventario['Nombre del Producto'].values:
            st.session_state.inventario = st.session_state.inventario[
                st.session_state.inventario['Nombre del Producto'] != nombre
            ]
            save_inventario(sheet, st.session_state.inventario)
            st.success(f"Producto '{nombre}' eliminado correctamente!")
            st.experimental_rerun()
        else:
            st.error(f"Producto '{nombre}' no encontrado en el inventario.")
    except Exception as e:
        st.error(f"Error al eliminar producto: {e}")

# Función para editar un producto
def editar_producto(nombre_original, nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo):
    try:
        if nombre_original in st.session_state.inventario['Nombre del Producto'].values:
            idx = st.session_state.inventario[
                st.session_state.inventario['Nombre del Producto'] == nombre_original
            ].index[0]
            
            st.session_state.inventario.at[idx, 'Nombre del Producto'] = nuevo_nombre
            st.session_state.inventario.at[idx, 'Stock'] = nuevo_stock
            st.session_state.inventario.at[idx, 'Precio'] = nuevo_precio
            st.session_state.inventario.at[idx, 'Costo'] = nuevo_costo
            
            save_inventario(sheet, st.session_state.inventario)
            st.success(f"Producto '{nombre_original}' actualizado correctamente!")
            st.experimental_rerun()
        else:
            st.error(f"Producto '{nombre_original}' no encontrado en el inventario.")
    except Exception as e:
        st.error(f"Error al editar producto: {e}")

# Función para sustraer stock
def sustraer_stock(nombre, cantidad):
    try:
        if nombre in st.session_state.inventario['Nombre del Producto'].values:
            idx = st.session_state.inventario[
                st.session_state.inventario['Nombre del Producto'] == nombre
            ].index[0]
            
            stock_actual = st.session_state.inventario.at[idx, 'Stock']
            
            if stock_actual >= cantidad:
                st.session_state.inventario.at[idx, 'Stock'] = stock_actual - cantidad
                save_inventario(sheet, st.session_state.inventario)
                st.success(f"Se sustrajeron {cantidad} unidades de '{nombre}'. Stock restante: {stock_actual - cantidad}")
                st.experimental_rerun()
            else:
                st.error(f"No hay suficiente stock de '{nombre}'. Stock actual: {stock_actual}")
        else:
            st.error(f"Producto '{nombre}' no encontrado en el inventario.")
    except Exception as e:
        st.error(f"Error al sustraer stock: {e}")

# Sidebar para operaciones
with st.sidebar:
    st.header("Operaciones de Inventario")
    opcion = st.radio(
        "Seleccione una operación:",
        ["Ver Inventario", "Agregar Producto", "Editar Producto", "Eliminar Producto", "Sustraer Stock"]
    )

# Mostrar inventario
if opcion == "Ver Inventario":
    st.header("📋 Inventario Actual")
    
    if st.session_state.inventario.empty:
        st.warning("El inventario está vacío.")
    else:
        # Calcular valor total y margen
        inventario = st.session_state.inventario.copy()
        inventario['Valor Total'] = inventario['Stock'] * inventario['Precio']
        inventario['Costo Total'] = inventario['Stock'] * inventario['Costo']
        inventario['Margen'] = inventario['Precio'] - inventario['Costo']
        inventario['Margen %'] = ((inventario['Precio'] - inventario['Costo']) / inventario['Precio'] * 100).round(2)
        
        st.dataframe(inventario.style.format({
            'Precio': '${:,.2f}',
            'Costo': '${:,.2f}',
            'Valor Total': '${:,.2f}',
            'Costo Total': '${:,.2f}',
            'Margen': '${:,.2f}',
            'Margen %': '{:.2f}%'
        }), use_container_width=True)
        
        # Resumen
        st.subheader("📊 Resumen del Inventario")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Productos", len(inventario))
        col2.metric("Valor Total Inventario", f"${inventario['Valor Total'].sum():,.2f}")
        col3.metric("Costo Total Inventario", f"${inventario['Costo Total'].sum():,.2f}")
        col4.metric("Margen Promedio", f"{inventario['Margen %'].mean():.2f}%")

# Agregar producto
elif opcion == "Agregar Producto":
    st.header("➕ Agregar Nuevo Producto")
    
    with st.form("agregar_producto_form"):
        nombre = st.text_input("Nombre del Producto*", key="add_nombre")
        col1, col2 = st.columns(2)
        stock = col1.number_input("Stock Inicial*", min_value=0, step=1, key="add_stock")
        precio = col1.number_input("Precio de Venta*", min_value=0.0, step=0.01, format="%.2f", key="add_precio")
        costo = col2.number_input("Costo del Producto*", min_value=0.0, step=0.01, format="%.2f", key="add_costo")
        
        submitted = st.form_submit_button("Agregar Producto")
        if submitted:
            if nombre.strip() and stock >=0 and precio >=0 and costo >=0:
                if nombre not in st.session_state.inventario['Nombre del Producto'].values:
                    agregar_producto(nombre, stock, precio, costo)
                else:
                    st.error("Ya existe un producto con ese nombre.")
            else:
                st.error("Por favor complete todos los campos obligatorios (*) correctamente.")

# Editar producto
elif opcion == "Editar Producto":
    st.header("✏️ Editar Producto Existente")
    
    if st.session_state.inventario.empty:
        st.warning("No hay productos para editar. El inventario está vacío.")
    else:
        producto_a_editar = st.selectbox(
            "Seleccione el producto a editar:",
            st.session_state.inventario['Nombre del Producto'].values,
            key="select_edit"
        )
        
        producto_data = st.session_state.inventario[
            st.session_state.inventario['Nombre del Producto'] == producto_a_editar
        ].iloc[0]
        
        with st.form("editar_producto_form"):
            nuevo_nombre = st.text_input("Nombre del Producto*", value=producto_data['Nombre del Producto'], key="edit_nombre")
            col1, col2 = st.columns(2)
            nuevo_stock = col1.number_input("Stock*", min_value=0, step=1, value=producto_data['Stock'], key="edit_stock")
            nuevo_precio = col1.number_input("Precio de Venta*", min_value=0.0, step=0.01, format="%.2f", 
                                          value=producto_data['Precio'], key="edit_precio")
            nuevo_costo = col2.number_input("Costo del Producto*", min_value=0.0, step=0.01, format="%.2f", 
                                         value=producto_data['Costo'], key="edit_costo")
            
            submitted = st.form_submit_button("Actualizar Producto")
            if submitted:
                if nuevo_nombre.strip() and nuevo_stock >=0 and nuevo_precio >=0 and nuevo_costo >=0:
                    if nuevo_nombre == producto_a_editar or nuevo_nombre not in st.session_state.inventario['Nombre del Producto'].values:
                        editar_producto(producto_a_editar, nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo)
                    else:
                        st.error("Ya existe otro producto con ese nombre.")
                else:
                    st.error("Por favor complete todos los campos obligatorios (*) correctamente.")

# Eliminar producto
elif opcion == "Eliminar Producto":
    st.header("🗑️ Eliminar Producto")
    
    if st.session_state.inventario.empty:
        st.warning("No hay productos para eliminar. El inventario está vacío.")
    else:
        producto_a_eliminar = st.selectbox(
            "Seleccione el producto a eliminar:",
            st.session_state.inventario['Nombre del Producto'].values,
            key="select_delete"
        )
        
        producto_data = st.session_state.inventario[
            st.session_state.inventario['Nombre del Producto'] == producto_a_eliminar
        ].iloc[0]
        
        st.warning(f"¿Está seguro que desea eliminar permanentemente este producto?")
        
        st.info(f"""
        **Detalles del producto:**
        - Nombre: {producto_data['Nombre del Producto']}
        - Stock actual: {producto_data['Stock']}
        - Precio: ${producto_data['Precio']:,.2f}
        - Costo: ${producto_data['Costo']:,.2f}
        """)
        
        if st.button("Confirmar Eliminación"):
            eliminar_producto(producto_a_eliminar)

# Sustraer stock
elif opcion == "Sustraer Stock":
    st.header("➖ Sustraer Stock")
    
    if st.session_state.inventario.empty:
        st.warning("No hay productos en el inventario.")
    else:
        producto_a_sustraer = st.selectbox(
            "Seleccione el producto:",
            st.session_state.inventario['Nombre del Producto'].values,
            key="select_subtract"
        )
        
        producto_data = st.session_state.inventario[
            st.session_state.inventario['Nombre del Producto'] == producto_a_sustraer
        ].iloc[0]
        
        st.info(f"""
        **Stock actual de '{producto_a_sustraer}':** {producto_data['Stock']}
        """)
        
        cantidad = st.number_input(
            "Cantidad a sustraer*", 
            min_value=1, 
            max_value=producto_data['Stock'], 
            step=1,
            key="input_subtract"
        )
        
        if st.button("Sustraer Stock"):
            sustraer_stock(producto_a_sustraer, cantidad)
