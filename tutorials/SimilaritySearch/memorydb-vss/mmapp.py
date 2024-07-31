import mmlib as glib
import streamlit as st
import time
# Streamlit page configuration
st.set_page_config(page_title="Semantic Search in Vector Database in Redis")
st.title("Semantic Search in Vector Database in Redis")

# Initialize Redis client
client_devo = glib.initialize_redis()

# Session state to track if vectors have been loaded
if 'vectors_loaded' not in st.session_state:
    st.session_state.vectors_loaded = False

# Function to load vectors and update the session state
def load_vectors():
    glib.loadVectorStore(client_devo)
    st.session_state.vectors_loaded = True
    st.write("Vector store loaded successfully.")

# Function to process and display question results
def ask_question(key):
    user_query = st.text_input("Enter your question:", "", key=key)
    if user_query:
        start_time2 = time.time()  # Start time
        results_df = glib.process_question(client_devo, user_query)
        end_time2 = time.time()  # End time
        if not results_df.empty:
            st.write("Results:")
            st.table(results_df)
            st.write(f"Time taken: {(end_time2 - start_time2):.2f} seconds")  # Display execution time
    
        else:
            st.write("No results found for the given query.")

# Check if the index is already created
index_exists = glib.check_index_existence(client_devo)

# Display options based on index existence and vectors loaded state
if index_exists['exists'] or st.session_state.vectors_loaded:
    st.write("Index available. You can ask questions.")
    ask_question(key="query_1")
elif not index_exists['exists']:
    st.write("Index not found.")
    load_button = st.button("Load Vectors into Store")
    if load_button:
        load_vectors()
        st.session_state.vectors_loaded = True  # Update the session state to reflect the loaded vectors

# Ensure the ask_question section is displayed after vectors are loaded
if st.session_state.vectors_loaded:
    ask_question(key="query_2")

# Rest of your Streamlit app logic...
