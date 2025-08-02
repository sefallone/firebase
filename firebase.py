import streamlit as st
import pandas as pd
from firebase_admin import credentials, firestore, initialize_app
import json

# ---------------------- Configuración de Firestore ---------------------- #

def init_firestore():
    if not hasattr(st.session_state, 'firestore_initialized'):
        cred = credentials.Certificate(json.loads(st.secrets["firebase"].to_dict()))
        initialize_app(cred)
        st.session_state.firestore_initialized = True
    return firestore.client()

db = init_firestore()

# ---------------------- Funciones de Firestore ---------------------- #

def get_inventory_collection():
    if 'selected_branch' not in st.session_state:
        st.error("Selecciona una sucursal primero.")
        return None
    return db.collection(f"inventario_{st.session_state.selected_branch.lower()}")

def load_inventory_once():
    col_ref = get_inventory_collection()
    if col_ref:
        docs = col_ref.stream()
        items = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            items.append(item)
        df = pd.DataFrame(items)
        for col in ['stock', 'precio', 'costo']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        if not df.empty:
            df = df.sort_values(by='nombre').reset_index(drop=True)
        st.session_state.items_data = df

def on_snapshot(col_snapshot, changes, read_time):
    items = []
    for doc in col_snapshot.documents:
        item = doc.to_dict()
        item['id'] = doc.id
        items.append(item)
    df = pd.DataFrame(items)
    for col in ['stock', 'precio', 'costo']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if not df.empty:
        df = df.sort_values(by='nombre').reset_index(drop=True)
    st.session_state.items_data = df

def setup_realtime_listener():
    if 'listener_initialized' not in st.session_state:
        col_ref = get_inventory_collection()
        if col_ref:
            col_ref.on_snapshot(on_snapshot)
            st.session_state.listener_initialized = True

def agregar_producto_firestore(nombre, stock, precio, costo):
    col_ref = get_inventory_collection()
    if col_ref:
        try:
            existing = col_ref.where('nombre', '==', nombre).stream()
            for _ in existing:
                st.warning("Ya existe un producto con ese nombre.")
                return False
            item_data = {
                "nombre": nombre,
                "stock": stock,
                "precio": precio,
                "costo": costo,
                "fecha_creacion": firestore.SERVER_TIMESTAMP
            }
            col_ref.add(item_data)
            st.success("Producto agregado correctamente.")
            load_inventory_once()
            return True
        except Exception as e:
            st.error(f"Error: {e}")
    return False

def update_item_firestore(item_id, nombre, stock, precio, costo):
    col_ref = get_inventory_collection()
    if col_ref:
        try:
            docs = col_ref.where('nombre', '==', nombre).stream()
            for doc in docs:
                if doc.id != item_id:
                    st.error("Ya existe otro producto con ese nombre.")
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
            st.success("Producto actualizado.")
            load_inventory_once()
            return True
        except Exception as e:
            st.error(f"Error al actualizar: {e}")
    return False

def delete_item_firestore(item_id):
    col_ref = get_inventory_collection()
    if col_ref:
        try:
            col_ref.document(item_id).delete()
            st.success("Producto eliminado.")
            load_inventory_once()
            return True
        except Exception as e:
            st.error(f"Error al eliminar: {e}")
    return False

# ---------------------- Interfaz Streamlit ---------------------- #

def seleccionar_sucursal():
    st.sidebar.title("Arte París - Inventario")
    sucursales = ["Centro", "Unicentro"]
    seleccion = st.sidebar.selectbox("Selecciona una sucursal:", sucursales)
    st.session_state.selected_branch = seleccion

def display_inventory():
    st.title(f"📦 Inventario - {st.session_state.selected_branch}")
    setup_realtime_listener()

    if st.button("🔄 Recargar Inventario Manualmente"):
        load_inventory_once()

    if 'items_data' not in st.session_state:
        st.info("Cargando inventario...")
        return

    productos = st.session_state.items_data.copy()

    if productos.empty:
        st.info("No hay productos registrados.")
        return

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

    with st.expander("🛠️ Editar / Eliminar Productos"):
        for _, row in productos.iterrows():
            with st.form(f"editar_{row['id']}"):
                col1, col2, col3, col4, col5 = st.columns(5)
                nuevo_nombre = col1.text_input("Nombre", value=row['nombre'], key=f"nombre_{row['id']}")
                nuevo_stock = col2.number_input("Stock", value=row['stock'], step=1, key=f"stock_{row['id']}")
                nuevo_precio = col3.number_input("Precio", value=row['precio'], step=100, key=f"precio_{row['id']}")
                nuevo_costo = col4.number_input("Costo", value=row['costo'], step=100, key=f"costo_{row['id']}")
                eliminar = col5.checkbox("Eliminar", key=f"eliminar_{row['id']}")
                enviar = st.form_submit_button("Guardar Cambios")

                if enviar:
                    if eliminar:
                        delete_item_firestore(row['id'])
                    else:
                        update_item_firestore(row['id'], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo)

# ---------------------- App Principal ---------------------- #

def main():
    seleccionar_sucursal()
    display_inventory()

if __name__ == '__main__':
    main()

