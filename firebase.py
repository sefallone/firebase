import streamlit as st
import pandas as pd
from datetime import datetime
import json 
from firebase_admin import credentials, initialize_app, auth, firestore
import firebase_admin


st.set_page_config(page_title="Prueba de Coneión Firestore", layout="wide")
st.title("📦 (Firestore)")



if 'firebase_initialized' not in st.session_state:
    st.session_state.firebase_initialized = False

if not st.session_state.firebase_initialized:
    try:
        firebase_service_account_info = {
            "type": st.secrets["firebase"]["type"],
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key_id": st.secrets["firebase"]["private_key_id"],
            "private_key": st.secrets["firebase"]["private_key"],
            "client_email": st.secrets["firebase"]["client_email"],
            "client_id": st.secrets["firebase"]["client_id"],
            "auth_uri": st.secrets["firebase"]["auth_uri"],
            "token_uri": st.secrets["firebase"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
            "universe_domain": st.secrets["firebase"]["universe_domain"]
        }
        
        # Inicializar credenciales con el certificado
        cred = credentials.Certificate(firebase_service_account_info)
        
        # Intentamos inicializar la app de Firebase si no está ya inicializada
        if not firebase_admin._apps:
            st.session_state.firebase_app = firebase_admin.initialize_app(cred)
        else:
            st.session_state.firebase_app = firebase_admin.get_app()

        st.session_state.db = firestore.client(st.session_state.firebase_app)
        st.session_state.auth = auth

        project_id = firebase_service_account_info.get("project_id", "unknown_project")
        st.session_state.user_id = f"streamlit_cloud_user_{project_id}" 

        st.session_state.firebase_initialized = True
        st.success("Firebase inicializado correctamente para Streamlit Cloud.")
    except Exception as e:
        st.error(f"Error al inicializar Firebase: {e}")
        st.warning("La aplicación puede no funcionar correctamente sin Firebase.")

# --- Funciones de Firestore (resto del código es el mismo) ---

def get_inventory_collection():
    """Obtiene la referencia a la colección de inventario."""
    if st.session_state.firebase_initialized:
        return st.session_state.db.collection("inventory_items")  # ✅ Accede a colección raíz correctamente
    return None


def add_item_firestore(nombre, stock, precio, costo):
    """Agrega un nuevo producto a Firestore."""
    col_ref = get_inventory_collection()
    if col_ref:
        try:
            docs = col_ref.where('nombre', '==', nombre).stream()
            if any(True for _ in docs):
                st.error(f"Ya existe un producto con el nombre '{nombre}'. Por favor, elija un nombre único.")
                return False

            item_data = {
                "nombre": nombre,
                "stock": stock,
                "precio": precio,
                "costo": costo,
                "fecha_actualizacion": firestore.SERVER_TIMESTAMP
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
            docs = col_ref.where('nombre', '==', nombre).stream()
            for doc in docs:
                if doc.id != item_id:
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
            item_ref.update(item_data)
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
        st.session_state.items_data = pd.DataFrame()

    col_ref = get_inventory_collection()
    if col_ref:
        if 'unsubscribe_inventory' in st.session_state and st.session_state.unsubscribe_inventory is not None:
            st.session_state.unsubscribe_inventory()
            st.session_state.unsubscribe_inventory = None

        def on_snapshot(col_snapshot, changes, read_time):
            current_items = []
            for doc in col_snapshot.documents:
                item = doc.to_dict()
                item['id'] = doc.id
                current_items.append(item)
            
            df = pd.DataFrame(current_items)
            
            for col in ['stock', 'precio', 'costo']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            if not df.empty:
                df = df.sort_values(by='nombre').reset_index(drop=True)

            st.session_state.items_data = df
            st.experimental_rerun()

        st.session_state.unsubscribe_inventory = col_ref.on_snapshot(on_snapshot)
        st.success("Listener de inventario en tiempo real activado.")
    else:
        st.warning("No se pudo configurar el listener de Firestore. Firebase no inicializado.")

# --- Interfaz de Usuario ---

def display_inventory():
    """Muestra el inventario actual con auto-actualización."""
    st.header("📊 Inventario Actual")

    if 'unsubscribe_inventory' not in st.session_state or st.session_state.unsubscribe_inventory is None:
        setup_realtime_listener()

    if st.session_state.items_data.empty:
        st.info("No hay productos registrados en el inventario.")
        return
    
    productos = st.session_state.items_data.copy()
    
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
                add_item_firestore(nombre, stock, precio, costo)

def edit_product_form():
    """Formulario para editar productos existentes."""
    st.header("✏️ Editar Producto")
    
    if 'unsubscribe_inventory' not in st.session_state or st.session_state.unsubscribe_inventory is None:
        setup_realtime_listener()

    productos = st.session_state.items_data
    
    if productos.empty:
        st.warning("No hay productos para editar.")
        return
    
    product_name_to_id = {row['nombre']: row['id'] for index, row in productos.iterrows()}
    
    producto_seleccionado_nombre = st.selectbox(
        "Seleccione un producto para editar:",
        list(product_name_to_id.keys()),
        key="select_edit_product"
    )
    
    if producto_seleccionado_nombre is None:
        return
    
    selected_item_id = product_name_to_id[producto_seleccionado_nombre]
    
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
                update_item_firestore(selected_item_id, nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo)

def delete_product_form():
    """Formulario para eliminar productos."""
    st.header("🗑️ Eliminar Producto")

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
        delete_item_firestore(selected_item_id)


# --- Menú Principal ---

def main():
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
        st.write(f"**ID de Usuario:** {st.session_state.get('user_id', 'Cargando...')}") 
        
        st.session_state.current_menu_selection = st.radio(
            "Seleccione una opción:",
            list(menu_options.keys()),
            key="main_menu_radio",
            index=list(menu_options.keys()).index(st.session_state.current_menu_selection)
        )
    
    menu_options[st.session_state.current_menu_selection]()

if __name__ == "__main__":
    main()


