import streamlit as st
import chatbot_lib as glib
import time

# Streamlit page configuration
st.title("MemoryDB as Vector Store")

# Initialize Redis client
client_devo = glib.initialize_redis()

# Check if the index exists
index_exists = glib.check_index_existence()
if index_exists['exists']:
    st.write("### Data already indexed: You can ask questions.")

    # Session state to control input visibility
    if 'show_second_inputs' not in st.session_state:
        st.session_state.show_second_inputs = False

    # Function to handle the first form submission
    def handle_first_form():
        user_name = st.session_state['user_name']
        question = st.session_state['question']
        if user_name and question:
            start_time1 = time.time()
            response = glib.askmeanything(question, user_name)
            end_time1 = time.time()
            st.session_state['response'] = response
            st.session_state['response_time'] = end_time1 - start_time1
            st.session_state.show_second_inputs = True

    # First form
    with st.form(key='first_form'):
        st.subheader("Customer Care Chat Interface")
        st.text("Please provide your name and ask a question.")
        user_name = st.text_input("Your Name", key='user_name')
        question = st.text_input("Ask a Question (without context):", key='question')
        submit_button = st.form_submit_button(label='Submit', on_click=handle_first_form)

    if 'response' in st.session_state:
        st.write("#### Response:")
        st.write(st.session_state['response'])
        st.write(f"Time taken: {st.session_state['response_time']:.2f} s")

    # Show second set of inputs only after the first form is submitted
    if st.session_state.show_second_inputs:
        with st.container():
            st.subheader("User Info Retrieval")
            st.text("Provide user info to retrieve specific data.")
            retrieval_question = st.text_input("User Info", key='retrieval_question')
            if retrieval_question:
                start_time2 = time.time()
                retrieval_response = glib.fetch_user_data(client_devo, retrieval_question)
                end_time2 = time.time()
                with st.expander("Retrieval Response:"):
                    st.write(retrieval_response)
                    st.write(f"Time taken: {(end_time2 - start_time2):.2f} seconds")

        with st.container():
            st.subheader("Similarity Search")
            st.text("Enter a query to perform a similarity search.")
            similarity_search = st.text_input("Similarity Search Query", key='similarity_search')
            if similarity_search:
                start_time = time.time()
                similarity_response = glib.perform_query(similarity_search)
                end_time = time.time()

                # Create two columns
                col1, col2 = st.columns(2)

                # In the first column, display the search response with each item on a new line
                with col1:
                    st.write("Search Response:")
                    for item in similarity_response:
                        st.write("Page Content:")
                        st.write(item.page_content)
                        st.text("")

                # In the second column, display the metadata (execution time in this case)
                with col2:
                    for item in similarity_response:
                        st.write("Metadata:")
                        st.write(item.metadata)
                        st.text("")
                    st.write(f"Time taken: {(end_time - start_time) * 1000:.2f} ms")

else:
    st.write("### Index does not exist. Initializing Vector Store...")
    # Code to initialize vector store
    start_time = time.time()
    vectorstore = glib.initializeVectorStore()
    end_time = time.time()
    st.write(f"Vector Store initialized in {end_time - start_time:.2f} seconds")
