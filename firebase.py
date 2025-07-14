import streamlit as st
import pandas as pd
from datetime import datetime
import json

# Importaciones de Firebase
# Asegúrate de que 'firebase-admin' esté en tu requirements.txt
from firebase_admin import credentials, initialize_app, auth, firestore
import firebase_admin

# --- Configuración de la aplicación Streamlit ---
st.set_page_config(page_title="Sistema de Inventario en Tiempo Real", layout="wide")
st.title("📦 Sistema de Gestión de Inventario en Tiempo Real (Firestore)")

# --- Inicialización de Firebase ---
# Usamos st.session_state para almacenar las instancias de Firebase
# para que no se reinicialicen en cada rerun de Streamlit.

if 'firebase_initialized' not in st.session_state:
    st.session_state.firebase_initialized = False

if not st.session_state.firebase_initialized:
    try:
        # --- Leer credenciales desde Streamlit Secrets ---
        # El contenido del archivo JSON de la clave de cuenta de servicio
        # se almacena como una cadena en st.secrets.firebase.service_account_key
        firebase_service_account_info = json.loads(st.secrets["firebase"]["service_account_key"])
        
        # Inicializar credenciales con el certificado
        cred = credentials.Certificate(firebase_service_account_info)
        
        # Intentamos inicializar la app de Firebase si no está ya inicializada
        if not firebase_admin._apps:
            st.session_state.firebase_app = firebase_admin.initialize_app(cred)
        else:
            st.session_state.firebase_app = firebase_admin.get_app()

        st.session_state.db = firestore.client(st.session_state.firebase_app)
        st.session_state.auth = auth

        # Para Streamlit Cloud, el userId se obtiene de la autenticación real del usuario.
        # Si no hay un usuario autenticado, podemos usar un ID de proyecto o un placeholder.
        # En una aplicación de producción real, implementarías un flujo de inicio de sesión.
        # Aquí, para que funcione sin un login explícito, usaremos un ID de proyecto o un ID anónimo.
        
        # Usaremos el project_id como parte del user_id para asegurar unicidad
        project_id = firebase_service_account_info.get("project_id", "unknown_project")
        st.session_state.user_id = f"streamlit_cloud_user_{project_id}" 
        # Opcional: Podrías generar un UUID para cada sesión si necesitas un ID de sesión único
        # import uuid
        # st.session_state.user_id = str(uuid.uuid4())

        st.session_state.firebase_initialized = True
        st.success("Firebase inicializado correctamente para Streamlit Cloud.")
    except Exception as e:
        st.error(f"Error al inicializar Firebase: {e}")
        st.warning("La aplicación puede no funcionar correctamente sin Firebase.")

# --- Funciones de Firestore ---

def get_inventory_collection():
    """Obtiene la referencia a la colección de inventario."""
    if st.session_state.firebase_initialized:
        # La ruta de la colección debe ser consistente con tus reglas de seguridad.
        # Usamos el project_id para crear una colección única por proyecto en Firestore.
        # Esto es útil si tienes múltiples aplicaciones usando el mismo Firebase.
        return st.session_state.db.collection(f"projects/{st.session_state.firebase_app.project_id}/inventory_items")
    return None

def add_item_firestore(nombre, stock, precio, costo):
    """Agrega un nuevo producto a Firestore."""
    col_ref = get_inventory_collection()
    if col_ref:
        try:
            # Verificar si el nombre ya existe (Firestore no tiene UNIQUE constraint)
            docs = col_ref.where('nombre', '==', nombre).stream()
            if any(True for _ in docs): # Si hay algún documento con ese nombre
                st.error(f"Ya existe un producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
                return False

            item_data = {
                "nombre": nombre,
                "stock": stock,
                "precio": precio,
                "costo": costo,
                "fecha_actualizacion": firestore.SERVER_TIMESTAMP # Usa el timestamp del servidor
            }
            col_ref.add(item_data)
            st.success("¡Producto agregado correctamente!")
            return True
        except Exception as e:
            st.error(f"Error al agregar producto: {e}")
            return False
    return False

def update_item_firestore(item_id, nombre, stock, precio, costo):
    """Actualiza un producto existente en Firestore."""
    col_ref = get_inventory_collection()
    if col_ref:
        try:
            # Verificar si el nuevo nombre ya existe en OTRO producto
            docs = col_ref.where('nombre', '==', nombre).stream()
            for doc in docs:
                if doc.id != item_id: # Si el nombre existe en un documento diferente
                    st.error(f"Ya existe otro producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
                    return False

            item_ref = col_ref.document(item_id)
            item_data = {
                "nombre": nombre,
                "stock": stock,
                "precio": precio,
                "costo": costo,
                "fecha_actualizacion": firestore.SERVER_TIMESTAMP
            }
            item_ref.update(item_data) # Usa update para modificar campos existentes
            st.success("¡Producto actualizado correctamente!")
            return True
        except Exception as e:
            st.error(f"Error al actualizar producto: {e}")
            return False
    return False

def delete_item_firestore(item_id):
    """Elimina un producto de Firestore."""
    col_ref = get_inventory_collection()
    if col_ref:
        try:
            col_ref.document(item_id).delete()
            st.success("¡Producto eliminado correctamente!")
            return True
        except Exception as e:
            st.error(f"Error al eliminar producto: {e}")
            return False
    return False

# --- Real-time Listener (onSnapshot) ---
def setup_realtime_listener():
    """Configura el listener en tiempo real para el inventario."""
    if 'items_data' not in st.session_state:
        st.session_state.items_data = pd.DataFrame() # Inicializa un DataFrame vacío

    col_ref = get_inventory_collection()
    if col_ref:
        # Si ya hay un listener activo, lo desuscribimos para evitar duplicados
        if 'unsubscribe_inventory' in st.session_state and st.session_state.unsubscribe_inventory is not None:
            st.session_state.unsubscribe_inventory()
            st.session_state.unsubscribe_inventory = None

        # Callback para cuando los datos cambian
        def on_snapshot(col_snapshot, changes, read_time):
            current_items = []
            for doc in col_snapshot.documents:
                item = doc.to_dict()
                item['id'] = doc.id # Añadir el ID del documento al diccionario
                current_items.append(item)
            
            df = pd.DataFrame(current_items)
            
            # Asegurarse de que las columnas numéricas sean del tipo correcto
            for col in ['stock', 'precio', 'costo']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0) # Convertir a numérico, NaN a 0

            # Ordenar por nombre para consistencia
            if not df.empty:
                df = df.sort_values(by='nombre').reset_index(drop=True)

            st.session_state.items_data = df
            # Forzar un rerun para actualizar la UI con los nuevos datos
            # Esto es crucial para que st.dataframe se actualice.
            st.experimental_rerun()

        # Configurar el listener y guardar la función de desuscripción
        st.session_state.unsubscribe_inventory = col_ref.on_snapshot(on_snapshot)
        st.success("Listener de inventario en tiempo real activado.")
    else:
        st.warning("No se pudo configurar el listener de Firestore. Firebase no inicializado.")

# --- Interfaz de Usuario ---

def display_inventory():
    """Muestra el inventario actual con auto-actualización."""
    st.header("📊 Inventario Actual")

    # Asegurarse de que el listener esté activo
    if 'unsubscribe_inventory' not in st.session_state or st.session_state.unsubscribe_inventory is None:
        setup_realtime_listener()

    if st.session_state.items_data.empty:
        st.info("No hay productos registrados en el inventario.")
        return
    
    productos = st.session_state.items_data.copy() # Trabajar con una copia para evitar SettingWithCopyWarning
    
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

def add_product_form():
    """Formulario para agregar nuevos productos."""
    st.header("➕ Agregar Nuevo Producto")
    
    with st.form("form_add_product", clear_on_submit=True):
        nombre = st.text_input("Nombre del Producto*")
        col1, col2 = st.columns(2)
        stock = col1.number_input("Stock Inicial*", min_value=0, value=0)
        precio = col1.number_input("Precio de Venta*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        costo = col2.number_input("Costo del Producto*", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        if st.form_submit_button("Agregar Producto"):
            if not nombre:
                st.error("El nombre del producto es obligatorio.")
            elif precio <= 0 or costo < 0:
                st.error("Precio de venta debe ser positivo y costo no puede ser negativo.")
            else:
                # La función add_item_firestore ya maneja el éxito/error y el rerun
                add_item_firestore(nombre, stock, precio, costo)

def edit_product_form():
    """Formulario para editar productos existentes."""
    st.header("✏️ Editar Producto")
    
    # Asegurarse de que el listener esté activo y los datos estén cargados
    if 'unsubscribe_inventory' not in st.session_state or st.session_state.unsubscribe_inventory is None:
        setup_realtime_listener()

    productos = st.session_state.items_data
    
    if productos.empty:
        st.warning("No hay productos para editar.")
        return
    
    # Crear un diccionario para mapear nombre a ID del documento
    product_name_to_id = {row['nombre']: row['id'] for index, row in productos.iterrows()}
    
    producto_seleccionado_nombre = st.selectbox(
        "Seleccione un producto para editar:",
        list(product_name_to_id.keys()),
        key="select_edit_product"
    )
    
    if producto_seleccionado_nombre is None:
        return
    
    # Obtener el ID del producto seleccionado
    selected_item_id = product_name_to_id[producto_seleccionado_nombre]
    
    # Obtener los datos del producto seleccionado del DataFrame
    producto_actual = productos[productos['id'] == selected_item_id].iloc[0]
    
    with st.form("form_edit_product"):
        nuevo_nombre = st.text_input("Nombre*", value=producto_actual['nombre'], key="edit_nombre")
        col1, col2 = st.columns(2)
        nuevo_stock = col1.number_input("Stock*", min_value=0, value=int(producto_actual['stock']), key="edit_stock")
        nuevo_precio = col1.number_input("Precio de Venta*", min_value=0.0, value=float(producto_actual['precio']), step=0.01, format="%.2f", key="edit_precio")
        nuevo_costo = col2.number_input("Costo del Producto*", min_value=0.0, value=float(producto_actual['costo']), step=0.01, format="%.2f", key="edit_costo")
        
        if st.form_submit_button("Actualizar Producto"):
            if not nuevo_nombre:
                st.error("El nombre del producto es obligatorio.")
            elif nuevo_precio <= 0 or nuevo_costo < 0:
                st.error("Precio de venta debe ser positivo y costo no puede ser negativo.")
            else:
                # La función update_item_firestore ya maneja el éxito/error y el rerun
                update_item_firestore(selected_item_id, nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo)

def delete_product_form():
    """Formulario para eliminar productos."""
    st.header("🗑️ Eliminar Producto")

    # Asegurarse de que el listener esté activo y los datos estén cargados
    if 'unsubscribe_inventory' not in st.session_state or st.session_state.unsubscribe_inventory is None:
        setup_realtime_listener()

    productos = st.session_state.items_data
    
    if productos.empty:
        st.warning("No hay productos para eliminar.")
        return
    
    product_name_to_id = {row['nombre']: row['id'] for index, row in productos.iterrows()}

    producto_a_eliminar_nombre = st.selectbox(
        "Seleccione un producto para eliminar:",
        list(product_name_to_id.keys()),
        key="select_delete_product"
    )

    if producto_a_eliminar_nombre is None:
        return

    selected_item_id = product_name_to_id[producto_a_eliminar_nombre]

    if st.button(f"Confirmar Eliminación de '{producto_a_eliminar_nombre}'", key="confirm_delete_button"):
        # La función delete_item_firestore ya maneja el éxito/error y el rerun
        delete_item_firestore(selected_item_id)


# --- Menú Principal ---

def main():
    # Inicializar el estado del menú si no existe
    if 'current_menu_selection' not in st.session_state:
        st.session_state.current_menu_selection = "Ver Inventario"

    menu_options = {
        "Ver Inventario": display_inventory,
        "Agregar Producto": add_product_form,
        "Editar Producto": edit_product_form,
        "Eliminar Producto": delete_product_form
    }
    
    with st.sidebar:
        st.title("Menú Principal")
        # Mostrar el ID de usuario (ahora basado en project_id)
        st.write(f"**ID de Usuario:** {st.session_state.get('user_id', 'Cargando...')}") 
        
        # El st.radio controla la selección del menú
        st.session_state.current_menu_selection = st.radio(
            "Seleccione una opción:",
            list(menu_options.keys()),
            key="main_menu_radio",
            index=list(menu_options.keys()).index(st.session_state.current_menu_selection)
        )
    
    # Ejecutar la función correspondiente a la opción seleccionada
    menu_options[st.session_state.current_menu_selection]()

if __name__ == "__main__":
    main()


