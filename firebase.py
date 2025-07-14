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
    """Obtiene productos con filtrado opcional por nombre"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            query = "SELECT * FROM productos"
            params = ()
            
            if filtro and filtro.strip():
                query += " WHERE nombre LIKE ?"
                params = (f'%{filtro.strip()}%',)
            
            query += " ORDER BY nombre"
            return pd.read_sql(query, conn, params=params)
            
    except sqlite3.Error as e:
        st.error(f"Error de base de datos: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        return pd.DataFrame()

def agregar_producto(nombre, stock, precio, costo):
    """Función corregida para agregar productos"""
    try:
        # Validaciones adicionales
        if not nombre or not nombre.strip():
            st.error("El nombre no puede estar vacío")
            return False
            
        if precio <= 0 or costo < 0:
            st.error("Precio debe ser positivo y costo no puede ser negativo")
            return False
            
        if precio <= costo:
            st.error("El precio debe ser mayor que el costo")
            return False

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Verificar si el producto ya existe
            cursor.execute("SELECT id FROM productos WHERE nombre = ?", (nombre.strip(),))
            if cursor.fetchone():
                st.error("Ya existe un producto con ese nombre")
                return False
                
            # Insertar nuevo producto
            cursor.execute(
                "INSERT INTO productos (nombre, stock, precio, costo) VALUES (?, ?, ?, ?)",
                (nombre.strip(), stock, precio, costo)
            )
            conn.commit()
            
            # Registrar en historial
            registrar_historial(
                cursor.lastrowid,
                "CREACIÓN",
                f"Stock: {stock}, Precio: {precio}, Costo: {costo}"
            )
            
            # Forzar actualización del inventario
            st.session_state.ultima_actualizacion = datetime.now()
            return True
            
    except sqlite3.Error as e:
        st.error(f"Error de base de datos: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
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
                (nombre, stock, precio, costo, id_producto))
                
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
    """Muestra el inventario con filtrado"""
    st.header("📋 Inventario Actual")
    
    # Widget de búsqueda
    filtro = st.text_input("🔍 Filtrar por nombre:", key="filtro_inventario")
    
    try:
        productos = obtener_productos(filtro)
        
        if productos.empty:
            st.warning("No hay productos registrados")
            return
            
        # Cálculos de métricas
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
            use_container_width=True,
            height=600
        )
        
    except Exception as e:
        st.error(f"Error al mostrar inventario: {str(e)}")

def mostrar_formulario_editar():
    """Formulario para editar productos con validación completa"""
    st.header("✏️ Editar Producto")
    
    # Obtener productos con manejo de errores
    try:
        productos = obtener_productos()
        if productos.empty:
            st.warning("No hay productos disponibles para editar")
            return
    except Exception as e:
        st.error(f"Error al cargar productos: {str(e)}")
        return
    
    # Seleccionar producto
    producto_seleccionado = st.selectbox(
        "Seleccione un producto a editar:",
        productos['nombre'],
        key="select_editar_producto"
    )
    
    if not producto_seleccionado:
        st.warning("Por favor seleccione un producto")
        return
    
    # Obtener datos del producto seleccionado
    producto = productos[productos['nombre'] == producto_seleccionado].iloc[0]
    
    # Formulario de edición
    with st.form(key="form_editar_producto", clear_on_submit=False):
        nuevo_nombre = st.text_input(
            "Nombre del producto*",
            value=producto['nombre'],
            key="editar_nombre"
        )
        
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input(
            "Cantidad en stock*",
            min_value=0,
            value=producto['stock'],
            step=1,
            key="editar_stock"
        )
        nuevo_precio = col1.number_input(
            "Precio de venta*",
            min_value=0.01,
            value=float(producto['precio']),
            step=0.01,
            format="%.2f",
            key="editar_precio"
        )
        nuevo_costo = col2.number_input(
            "Costo unitario*",
            min_value=0.0,
            value=float(producto['costo']),
            step=0.01,
            format="%.2f",
            key="editar_costo"
        )
        
        # Validación antes de enviar
        submitted = st.form_submit_button("Guardar Cambios")
        if submitted:
            if not nuevo_nombre.strip():
                st.error("El nombre del producto es obligatorio")
                st.stop()
                
            if nuevo_precio <= 0:
                st.error("El precio debe ser mayor que 0")
                st.stop()
                
            if nuevo_costo < 0:
                st.error("El costo no puede ser negativo")
                st.stop()
                
            if nuevo_precio <= nuevo_costo:
                st.error("El precio debe ser mayor que el costo")
                st.stop()
            
            # Confirmación adicional
            confirmar = st.checkbox("Confirmo que deseo actualizar este producto", False)
            if not confirmar:
                st.warning("Por favor confirme los cambios")
                st.stop()
            
            # Ejecutar actualización
            if actualizar_producto(
                producto['id'],
                nuevo_nombre.strip(),
                nuevo_stock,
                nuevo_precio,
                nuevo_costo
            ):
                st.success("Producto actualizado exitosamente!")
                st.session_state.ultima_actualizacion = datetime.now()
                
                # Opción para volver al inventario
                if st.button("Volver al Inventario"):
                    st.session_state.main_menu = "Ver Inventario"
                    st.rerun()
            else:
                st.error("Error al actualizar el producto")



def mostrar_formulario_agregar():
    """Formulario corregido para agregar productos"""
    st.header("➕ Agregar Nuevo Producto")
    
    with st.form("form_agregar", clear_on_submit=True):
        nombre = st.text_input("Nombre del Producto*", key="nombre_add")
        stock = st.number_input("Stock Inicial*", min_value=0, value=0, step=1, key="stock_add")
        precio = st.number_input("Precio de Venta*", min_value=0.01, value=0.01, step=0.01, format="%.2f", key="precio_add")
        costo = st.number_input("Costo Unitario*", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="costo_add")
        
        if st.form_submit_button("Agregar Producto"):
            if not nombre.strip():
                st.error("El nombre es obligatorio")
            elif precio <= costo:
                st.error("El precio debe ser mayor que el costo")
            else:
                if agregar_producto(nombre, stock, precio, costo):
                    st.success("Producto agregado correctamente!")
                    # Esperar 1 segundo antes de refrescar
                    time.sleep(1)
                    st.rerun()

def obtener_productos():
    """Función mejorada para obtener productos"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # Usar parámetros para evitar SQL injection
            query = "SELECT id, nombre, stock, precio, costo, fecha_actualizacion FROM productos ORDER BY nombre"
            return pd.read_sql(query, conn)
    except sqlite3.Error as e:
        st.error(f"Error al cargar productos: {str(e)}")
        return pd.DataFrame()  # Retornar DataFrame vacío en caso de error

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
    
    # Opciones del menú
    MENU_OPTIONS = {
        "Ver Inventario": mostrar_inventario,
        "Agregar Producto": mostrar_formulario_agregar,
        "Editar Producto": mostrar_formulario_editar,
        "Historial": mostrar_historial
    }
    
    # Sidebar
    with st.sidebar:
        st.title("Menú Principal")
        selected = st.radio(
            "Opciones:",
            list(MENU_OPTIONS.keys()),
            index=list(MENU_OPTIONS.keys()).index(st.session_state.main_menu)
        )
        
        # Mostrar info de la base de datos
        try:
            with sqlite3.connect(DB_FILE) as conn:
                count = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
                st.caption(f"Productos registrados: {count}")
        except:
            st.caption("No se pudo conectar a la base de datos")
    
    # Mostrar contenido seleccionado
    try:
        MENU_OPTIONS[selected]()
    except Exception as e:
        st.error(f"Error al cargar la sección: {str(e)}")
        st.session_state.main_menu = "Ver Inventario"
        st.rerun()
if __name__ == "__main__":
    main()
