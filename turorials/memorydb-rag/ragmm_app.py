import streamlit as st
import ragmm_lib as glib
import time
import pandas as pd
# Streamlit page configuration
st.set_page_config(page_title="RAG using MemoryDB as Vector Database")
st.title("RAG using MemoryDB as Vector Database")

# Initialize Redis client
client_devo = glib.initialize_redis()

# Check if the index exists
index_exists = glib.check_index_existence()
if index_exists['exists']:
    st.write("Data already indexed:  You can ask questions.")

    # No Context Question
    question = st.text_input("Ask a question: Note here application doesnt have any context:")
    if question:
        start_time1 = time.time()  # Start time
        response = glib.noContext(question)
        end_time1 = time.time()  # End time
        st.write("Response:", response)
        st.write(f"Time taken: {(end_time1 - start_time1):.2f} s")  # Display execution time

    # Retrieval-based Question
    retrieval_question = st.text_input("Now lets see what response is if we add context with RAG")
    if retrieval_question:
        start_time2 = time.time()  # Start time
        retrieval_response = glib.query_and_get_response(retrieval_question)
        end_time2 = time.time()  # End time
        st.write("Retrieval Response:", retrieval_response)
        st.write(f"Time taken: {(end_time2 - start_time2):.2f} seconds")  # Display execution time
    
    similarity_search = st.text_input("This is to show resonse only for a similarity search and source ")
    if similarity_search:
        start_time = time.time()  # Start time
        similarity_response = glib.perform_query(similarity_search)
        end_time = time.time()  # End time

        # Create two columns
        col1, col2 = st.columns(2)

        # In the first column, display the search response with each item on a new line
        with col1:
            st.write("Search Response:")
            for item in similarity_response:  # Assuming similarity_response is iterable
                st.write("Page Content:")
                st.write(item.page_content)
                st.text("") 

        # In the second column, display the metadata (execution time in this case)
        with col2:
            for item in similarity_response:  # Assuming similarity_response is iterable
                st.write("Metadata:")
                st.write(item.metadata)
                st.text("") 
            st.write(f"Time taken: {(end_time - start_time)*1000:.2f} ms")  # Display execution time


else:
    st.write("Index does not exist. Initializing Vector Store...")
    # Code to initialize vector store
    # You need to define how you get `pdf_path` and `embeddings` for the function call
    start_time = time.time()
    
    vectorstore = glib.initializeVectorStore()
    end_time = time.time()
    st.write(f"Vector Store initialized in {end_time - start_time:.2f} seconds")
