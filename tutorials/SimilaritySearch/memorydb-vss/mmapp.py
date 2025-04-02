import streamlit as st
import logging
import mmlib as glib
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Streamlit app
def main():
    st.title("MemoryDB Vector Search Demo")
    st.write("This is a test message. If you can see this, Streamlit is working.")

    logging.info("Initializing Redis connection")
    client = glib.initialize_redis()

    if client is None:
        st.error("Failed to connect to MemoryDB. Please check your connection settings.")
        return

    # Check if data is already loaded
    index_status = glib.check_index_existence(client)
    if not index_status['exists']:
        st.warning("No data found in MemoryDB. Loading data...")
        try:
            glib.loadVectorStore(client)
            st.success("Data loaded successfully!")
        except Exception as e:
            st.error(f"Error loading data: {e}")
            logging.error(f"Error loading data: {e}", exc_info=True)
            return
    else:
        st.info(f"Found {index_status['num_docs']} documents in MemoryDB.")

    # User input
    user_query = st.text_input("Enter your question:")

    if user_query:
        try:
            results_df = glib.process_question(client, user_query)
            if not results_df.empty:
                st.write("Top 5 similar questions and answers:")
                st.dataframe(results_df)
            else:
                st.write("No similar questions found.")
        except Exception as e:
            st.error(f"Error processing question: {e}")
            logging.error(f"Error processing question: {e}", exc_info=True)

if __name__ == "__main__":
    logging.info("Starting Streamlit app")
    main()
