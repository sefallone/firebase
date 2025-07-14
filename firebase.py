# Importaciones necesarias
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema de Inventario Avanzado",
    layout="wide",
    page_icon="📊"
)
st.title("📦 Sistema de Gestión de Inventario Avanzado")

# Configuración de la base de datos
DB_FILE = "inventario.db"

# ------------------------------------------
# FUNCIONES DE BASE DE DATOS MEJORADAS
# ------------------------------------------

def init_db():
    """Inicializa la base de datos con tablas y constraints mejorados"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                precio REAL NOT NULL CHECK(precio > 0),
                costo REAL NOT NULL CHECK(costo >= 0),
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (precio >= costo)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                operacion TEXT NOT NULL,
                detalles TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(producto_id) REFERENCES productos(id)
            )
        ''')

def registrar_historial(producto_id, operacion, detalles=None):
    """Registra una operación en el historial de cambios"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO historial (producto_id, operacion, detalles) VALUES (?, ?, ?)",
            (producto_id, operacion, detalles)
        )

def obtener_productos(filtro=None):
    """Obtiene productos con opción a filtrado, devuelve DataFrame"""
    query = "SELECT * FROM productos"
    params = ()
    
    if filtro and filtro.strip():
        query += " WHERE nombre LIKE ?"
        params = (f'%{filtro}%',)
    
    query += " ORDER BY nombre"
    
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql(query, conn, params=params)

def agregar_producto(nombre, stock, precio, costo):
    """Agrega un nuevo producto con validaciones completas"""
    with sqlite3.connect(DB_FILE) as conn:
        try:
            # Validación de negocio
            if precio < costo:
                st.error("ERROR: El precio no puede ser menor que el costo")
                return False
                
            cursor = conn.cursor()
            
            # Verificar duplicados
            cursor.execute("SELECT id FROM productos WHERE nombre=?", (nombre,))
            if cursor.fetchone():
                st.error(f"ERROR: El producto '{nombre}' ya existe")
                return False
                
            # Insertar nuevo producto
            cursor.execute(
                "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
                (nombre, stock, precio, costo)
            )
            producto_id = cursor.lastrowid
            
            # Registrar en historial
            registrar_historial(
                producto_id,
                "CREACIÓN",
                f"Stock: {stock}, Precio: {precio}, Costo: {costo}"
            )
            
            st.session_state.ultima_actualizacion = datetime.now()
            return True
            
        except sqlite3.Error as e:
            st.error(f"ERROR de base de datos: {str(e)}")
            return False

def actualizar_producto(id_producto, nombre, stock, precio, costo):
    """Actualiza un producto existente con validaciones"""
    with sqlite3.connect(DB_FILE) as conn:
        try:
            if precio < costo:
                st.error("ERROR: El precio no puede ser menor que el costo")
                return False
                
            cursor = conn.cursor()
            
            # Verificar duplicados (excluyendo el actual)
            cursor.execute(
                "SELECT id FROM productos WHERE nombre=? AND id != ?",
                (nombre, id_producto)
            )
            if cursor.fetchone():
                st.error(f"ERROR: Ya existe otro producto con nombre '{nombre}'")
                return False
                
            # Obtener datos anteriores para el historial
            cursor.execute(
                "SELECT nombre, stock, precio, costo FROM productos WHERE id=?",
                (id_producto,)
            )
            old_data = cursor.fetchone()
            
            # Actualizar producto
            cursor.execute(
                """UPDATE productos 
                SET nombre=?, stock=?, precio=?, costo=?, fecha_actualizacion=CURRENT_TIMESTAMP 
                WHERE id=?""",
                (nombre, stock, precio, costo, id_producto)
                
            # Registrar cambios en historial
            cambios = []
            if old_data[0] != nombre: cambios.append(f"Nombre: {old_data[0]} → {nombre}")
            if old_data[1] != stock: cambios.append(f"Stock: {old_data[1]} → {stock}")
            if old_data[2] != precio: cambios.append(f"Precio: {old_data[2]} → {precio}")
            if old_data[3] != costo: cambios.append(f"Costo: {old_data[3]} → {costo}")
            
            if cambios:
                registrar_historial(
                    id_producto,
                    "ACTUALIZACIÓN",
                    ", ".join(cambios)
                )
            
            st.session_state.ultima_actualizacion = datetime.now()
            return True
            
        except sqlite3.Error as e:
            st.error(f"ERROR de base de datos: {str(e)}")
            return False

# ------------------------------------------
# COMPONENTES DE INTERFAZ MEJORADOS
# ------------------------------------------

def mostrar_inventario():
    """Muestra el inventario con opciones de filtrado y métricas"""
    st.header("📋 Inventario Actual")
    
    # Filtrado y búsqueda
    col1, col2 = st.columns([3, 1])
    filtro = col1.text_input("🔍 Buscar producto por nombre:")
    mostrar_metricas = col2.checkbox("Mostrar métricas", True)
    
    productos = obtener_productos(filtro)
    
    if productos.empty:
        st.warning("No se encontraron productos")
        return
    
    # Cálculo de métricas
    productos['Valor Total'] = productos['stock'] * productos['precio']
    productos['Costo Total'] = productos['stock'] * productos['costo']
    productos['Margen'] = productos['precio'] - productos['costo']
    productos['Margen %'] = (productos['Margen'] / productos['precio'] * 100).round(2)
    
    # Mostrar métricas resumidas
    if mostrar_metricas:
        total_valor = productos['Valor Total'].sum()
        total_costo = productos['Costo Total'].sum()
        margen_promedio = productos['Margen %'].mean()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Valor Total Inventario", f"${total_valor:,.2f}")
        m2.metric("Costo Total Inventario", f"${total_costo:,.2f}")
        m3.metric("Margen Promedio", f"{margen_promedio:.2f}%")
    
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
        use_container_width=True,
        height=600
    )

def mostrar_formulario_agregar():
    """Formulario para agregar productos con validación mejorada"""
    st.header("➕ Agregar Nuevo Producto")
    
    with st.form("form_agregar", clear_on_submit=True):
        nombre = st.text_input("Nombre del Producto*", max_chars=100)
        
        col1, col2 = st.columns(2)
        stock = col1.number_input("Stock Inicial*", min_value=0, value=0, step=1)
        precio = col1.number_input("Precio de Venta*", min_value=0.01, value=1.0, step=0.01, format="%.2f")
        costo = col2.number_input("Costo Unitario*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        submitted = st.form_submit_button("Agregar Producto")
        if submitted:
            if not nombre.strip():
                st.error("El nombre del producto es obligatorio")
            elif precio <= costo:
                st.error("El precio debe ser mayor que el costo")
            else:
                if agregar_producto(nombre, stock, precio, costo):
                    st.success("✅ Producto agregado correctamente")
                    st.session_state.main_menu = "Ver Inventario"
                    st.rerun()

def mostrar_formulario_editar():
    """Formulario para editar productos con confirmación"""
    st.header("✏️ Editar Producto Existente")
    
    productos = obtener_productos()
    if productos.empty:
        st.warning("No hay productos registrados para editar")
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
        nuevo_stock = col1.number_input("Stock*", min_value=0, value=producto['stock'], step=1)
        nuevo_precio = col1.number_input("Precio*", min_value=0.01, value=producto['precio'], step=0.01, format="%.2f")
        nuevo_costo = col2.number_input("Costo*", min_value=0.0, value=producto['costo'], step=0.01, format="%.2f")
        
        confirmar = st.checkbox("Confirmar cambios", False)
        submitted = st.form_submit_button("Actualizar Producto")
        
        if submitted and confirmar:
            if not nuevo_nombre.strip():
                st.error("El nombre del producto es obligatorio")
            elif nuevo_precio <= nuevo_costo:
                st.error("El precio debe ser mayor que el costo")
            else:
                if actualizar_producto(
                    producto['id'], 
                    nuevo_nombre, 
                    nuevo_stock, 
                    nuevo_precio, 
                    nuevo_costo
                ):
                    st.success("✅ Producto actualizado correctamente")
                    st.session_state.main_menu = "Ver Inventario"
                    st.rerun()
        elif submitted and not confirmar:
            st.error("Por favor confirme los cambios marcando la casilla")

def mostrar_historial():
    """Muestra el historial de cambios del sistema"""
    st.header("🕒 Historial de Operaciones")
    
    with sqlite3.connect(DB_FILE) as conn:
        historial = pd.read_sql('''
            SELECT h.fecha, p.nombre as producto, h.operacion, h.detalles 
            FROM historial h
            JOIN productos p ON h.producto_id = p.id
            ORDER BY h.fecha DESC
            LIMIT 100
        ''', conn)
    
    if historial.empty:
        st.info("No hay registros históricos aún")
    else:
        st.dataframe(
            historial,
            use_container_width=True,
            column_config={
                "fecha": "Fecha/Hora",
                "producto": "Producto",
                "operacion": "Operación",
                "detalles": "Detalles"
            }
        )

# ------------------------------------------
# MENÚ PRINCIPAL Y EJECUCIÓN
# ------------------------------------------

def main():
    # Inicializar base de datos
    init_db()
    
    # Inicializar estado de sesión
    if 'main_menu' not in st.session_state:
        st.session_state.main_menu = "Ver Inventario"
    
    # Definir opciones del menú
    MENU_OPTIONS = {
        "Ver Inventario": mostrar_inventario,
        "Agregar Producto": mostrar_formulario_agregar,
        "Editar Producto": mostrar_formulario_editar,
        "Historial": mostrar_historial
    }
    
    # Sidebar con menú
    with st.sidebar:
        st.title("Menú Principal")
        st.image("https://via.placeholder.com/150x50?text=Inventario", width=150)
        
        selected = st.radio(
            "Opciones:",
            list(MENU_OPTIONS.keys()),
            index=list(MENU_OPTIONS.keys()).index(st.session_state.main_menu)
        )
        
        st.session_state.main_menu = selected
        
        # Mostrar última actualización
        if 'ultima_actualizacion' in st.session_state:
            st.caption(f"Última actualización: {st.session_state.ultima_actualizacion.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Mostrar contenido seleccionado
    MENU_OPTIONS[selected]()

if __name__ == "__main__":
    main()
