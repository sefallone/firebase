import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

# ---------- CONFIGURACIÓN FIRESTORE ----------
@st.cache_resource
def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(st.secrets["firebase"])
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firestore()

# ---------- SELECCIÓN DE SUCURSAL ----------
st.set_page_config(page_title="Inventario Arte París", layout="wide")
st.title("🧁 Arte París - Inventario")

sucursales = ["Centro", "Unicentro"]
if "selected_branch" not in st.session_state:
    st.session_state.selected_branch = sucursales[0]

st.selectbox("Selecciona la sucursal", sucursales, key="selected_branch")

# ---------- UTILIDADES ----------
def get_inventory_collection():
    return db.collection(f"inventario_{st.session_state.selected_branch.lower()}")

def load_inventory_once():
    col_ref = get_inventory_collection()
    docs = col_ref.stream()
    items = []
    for doc in docs:
        item = doc.to_dict()
        item["id"] = doc.id
        items.append(item)
    df = pd.DataFrame(items)
    for col in ["stock", "precio", "costo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if not df.empty:
        df = df.sort_values(by="nombre").reset_index(drop=True)
    st.session_state.items_data = df

def on_snapshot(col_snapshot, changes, read_time):
    items = []
    for doc in col_snapshot.documents:
        item = doc.to_dict()
        item["id"] = doc.id
        items.append(item)
    df = pd.DataFrame(items)
    for col in ["stock", "precio", "costo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if not df.empty:
        df = df.sort_values(by="nombre").reset_index(drop=True)
    st.session_state.items_data = df

def setup_realtime_listener():
    if "listener_initialized" not in st.session_state:
        col_ref = get_inventory_collection()
        if col_ref:
            col_ref.on_snapshot(on_snapshot)
            st.session_state.listener_initialized = True

# ---------- CRUD ----------
def agregar_producto_firestore(nombre, stock, precio, costo):
    col_ref = get_inventory_collection()
    try:
        existing = col_ref.where("nombre", "==", nombre).stream()
        for _ in existing:
            st.warning("Ya existe un producto con ese nombre.")
            return False
        item_data = {
            "nombre": nombre,
            "stock": stock,
            "precio": precio,
            "costo": costo,
            "fecha_creacion": firestore.SERVER_TIMESTAMP,
        }
        col_ref.add(item_data)
        st.success("Producto agregado.")
        load_inventory_once()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def update_item_firestore(item_id, nombre, stock, precio, costo):
    col_ref = get_inventory_collection()
    try:
        docs = col_ref.where("nombre", "==", nombre).stream()
        for doc in docs:
            if doc.id != item_id:
                st.error("Ya existe otro producto con ese nombre.")
                return False
        col_ref.document(item_id).update({
            "nombre": nombre,
            "stock": stock,
            "precio": precio,
            "costo": costo,
            "fecha_actualizacion": firestore.SERVER_TIMESTAMP,
        })
        st.success("Producto actualizado.")
        load_inventory_once()
        return True
    except Exception as e:
        st.error(f"Error al actualizar: {e}")
        return False

def delete_item_firestore(item_id):
    col_ref = get_inventory_collection()
    try:
        col_ref.document(item_id).delete()
        st.success("Producto eliminado.")
        load_inventory_once()
        return True
    except Exception as e:
        st.error(f"Error al eliminar: {e}")
        return False

# ---------- LISTENER & RECARGA ----------
setup_realtime_listener()

st.divider()
st.subheader("📦 Inventario")

if st.button("🔄 Recargar Inventario Manualmente"):
    load_inventory_once()

if "items_data" not in st.session_state:
    load_inventory_once()

productos = st.session_state.get("items_data", pd.DataFrame())

if productos.empty:
    st.info("No hay productos.")
else:
    productos["Valor Total"] = productos["stock"] * productos["precio"]
    productos["Costo Total"] = productos["stock"] * productos["costo"]
    productos["Margen"] = productos["precio"] - productos["costo"]
    productos["Margen %"] = (productos["Margen"] / productos["precio"] * 100).round(2)

    st.dataframe(
        productos.style.format({
            "precio": "${:,.2f}",
            "costo": "${:,.2f}",
            "Valor Total": "${:,.2f}",
            "Costo Total": "${:,.2f}",
            "Margen": "${:,.2f}",
            "Margen %": "{:.2f}%",
        }),
        use_container_width=True
    )

    st.subheader("✏️ Editar / 🗑️ Eliminar productos")
    for _, row in productos.iterrows():
        with st.expander(f"{row['nombre']}"):
            with st.form(key=f"form_{row['id']}"):
                nuevo_nombre = st.text_input("Nombre", value=row["nombre"])
                nuevo_stock = st.number_input("Stock", value=int(row["stock"]), min_value=0)
                nuevo_precio = st.number_input("Precio venta", value=float(row["precio"]), min_value=0.0)
                nuevo_costo = st.number_input("Precio costo", value=float(row["costo"]), min_value=0.0)
                col1, col2 = st.columns(2)
                if col1.form_submit_button("Guardar cambios"):
                    update_item_firestore(row["id"], nuevo_nombre, nuevo_stock, nuevo_precio, nuevo_costo)
                if col2.form_submit_button("Eliminar producto"):
                    delete_item_firestore(row["id"])

# ---------- AGREGAR PRODUCTO ----------
st.divider()
st.subheader("➕ Agregar nuevo producto")

with st.form("add_form"):
    nombre_nuevo = st.text_input("Nombre")
    stock_nuevo = st.number_input("Stock", min_value=0, step=1)
    precio_nuevo = st.number_input("Precio venta", min_value=0.0)
    costo_nuevo = st.number_input("Precio costo", min_value=0.0)
    if st.form_submit_button("Agregar"):
        agregar_producto_firestore(nombre_nuevo, stock_nuevo, precio_nuevo, costo_nuevo)

