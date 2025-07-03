import streamlit as st

 
st.title('Mi Primera Aplicación Web con Streamlit')
name = st.text_input('Introduce tu nombre', 'John Doe')
st.write(f'Hola, {name}!')
