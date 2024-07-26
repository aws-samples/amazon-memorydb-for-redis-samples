import streamlit as st
import ragmm_lib as glib
import pandas as pd

# Streamlit page configuration
st.set_page_config(page_title="Using MemoryDB as Vector Database")
st.title("Using MemoryDB as Vector Database")

# Initialize Redis client
client_devo = glib.initialize_memorydb()

# Check if the index exists
index_exists = glib.check_index_existence()

if index_exists['exists']:
    st.write("Data already indexed: You can ask questions.")

    with st.form("question_form"):
        question = st.text_input("Ask a question:")
        similarity_search = st.text_input("Similarity search:")
        submitted = st.form_submit_button("Submit")

    if submitted:
        if question:
            # No Context Question
            response = glib.noContext(question)
            
            # Retrieval-based Question
            retrieval_response = glib.query_and_get_response(question)
            
            # Display responses side by side
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("No Context Response")
                st.write(response)
            
            with col2:
                st.subheader("Response with Context")
                st.write(retrieval_response)
        
        if similarity_search:
            similarity_response = glib.perform_query(similarity_search)
            
            # Create two columns for similarity search response and metadata
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Similarity Search Response")
                for item in similarity_response:  # Assuming similarity_response is iterable
                    st.write("Page Content:")
                    st.write(item.page_content)
                    st.text("") 
            
            with col2:
                st.subheader("Metadata")
                for item in similarity_response:  # Assuming similarity_response is iterable
                    st.write(item.metadata)
                    st.text("") 
        
else:
    st.write("Index does not exist. Initializing Vector Store...")
    # Code to initialize vector store
    # You need to define how you get `pdf_path` and `embeddings` for the function call
    vectorstore = glib.initializeVectorStore()
    
