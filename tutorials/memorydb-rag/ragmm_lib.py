import os
import redis
import time
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain_aws.embeddings import BedrockEmbeddings
from langchain.chains import ConversationChain
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_aws.vectorstores.inmemorydb import InMemoryVectorStore
from redis.cluster import RedisCluster as MemoryDBCluster
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
load_dotenv()


# Constants
MEMORYDB_CLUSTER = os.environ.get("MEMORYDB_CLUSTER")
INDEX_NAME = 'idx:vss-mm'
MEMORYDB_CLUSTER_URL = f"rediss://{MEMORYDB_CLUSTER}:6379/ssl=True&ssl_cert_reqs=none"
pdf_path= "memorydb-guide.pdf"


def initialize_memorydb():
    configs = get_configs()
    client=MemoryDBCluster(
           host=configs['MEMORYDB_CLUSTER'], 
           port=6379,
           ssl=True, 
           decode_responses=True, 
           ssl_cert_reqs="none")
    try:
        client.ping()
        print("Connection to MemoryDB successful")
        return client
    except Exception as e:
        print("An error occurred while connecting to MemoryDB:", e)
        return None

def get_configs():
    configs = {}
    configs['MEMORYDB_CLUSTER'] = os.environ.get("MEMORYDB_CLUSTER")
    return configs


# Initialize Bedrock model
def get_llm():
    # create the Anthropic Model
    model_kwargs = {
    "temperature": 0, 
    "top_k": 250, 
    "top_p": 1,
    "stop_sequences": ["\\n\\nHuman:"]
    }    
    configs = get_configs()
    llm = ChatBedrock(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    model_kwargs=model_kwargs
    )
    return llm
    
    
# Initialize embeddings
def initialize_embeddings():
    #configs = get_configs()
    embeddings = BedrockEmbeddings()
    return embeddings
    
    
def check_index_existence():
    try:
        client=initialize_memorydb()
        info = client.ft(INDEX_NAME).info()
        num_docs = info.get('num_docs', 'N/A')
        space_usage = info.get('space_usage', 'N/A')
        num_indexed_vectors = info.get('num_indexed_vectors', 'N/A')
        vector_space_usage = info.get('vector_space_usage', 'N/A')
        index_details = {
            'num_docs': num_docs,
            'space_usage': space_usage,
            'num_indexed_vectors': num_indexed_vectors,
            'vector_space_usage': vector_space_usage,
            'exists': True
        }
        return index_details
    except Exception:
        return {'exists': False}


def initializeVectorStore():
    # Start measuring the execution time of the function
    start_time = time.time()
    embeddings = initialize_embeddings()
    try:
        # Load and split PDF
        # Initialize the PDF loader with the specified file path
        loader = PyPDFLoader(file_path=pdf_path)
        # Load the PDF pages
        pages = loader.load_and_split()
        # Define the text splitter settings for chunking the text
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", " "],
            chunk_size=1000,
            chunk_overlap=100
        )
        # Split the text into chunks using the defined splitter
        chunks = loader.load_and_split(text_splitter)
        # Create MemoryDB vector store
        # Initialize the MemoryDB vector store with the chunks and embedding details
        vectorstore = InMemoryVectorStore.from_documents(
            chunks,
            embedding=embeddings,
            redis_url=MEMORYDB_CLUSTER_URL,
            index_name=INDEX_NAME,
        )
        # Calculate and print the execution time upon successful completion
        end_time = time.time()
        print(f"initializeVectorStore() executed in {end_time - start_time:.2f} seconds")
        return vectorstore
    except Exception as e:
        # Handle any exceptions that occur during execution
        # Calculate and print the execution time till the point of failure
        end_time = time.time()
        print(f"Error occurred during initializeVectorStore(): {e}")
        print(f"Failed execution time: {end_time - start_time:.2f} seconds")
        # Return None to indicate failure
        return None


def initializeRetriever():
    """
    Initializes a Redis instance as a retriever for an existing vector store.

    :param redis_url: The URL of the Redis instance.
    :param index_name: The name of the index in the Redis vector store.
    :param embeddings: The embeddings to use for the retriever.
    :param index_schema: (Optional) The index schema, if needed.
    :return: The retriever object or None in case of an error.
    """
    index_name = INDEX_NAME
    redis_url = MEMORYDB_CLUSTER_URL
    embeddings = initialize_embeddings()
    try:
        # Start measuring time for MemoryDB initialization
        start_time_redis = time.time()
        # Initialize the MemoryDB instance with the given parameters
        # Measure and print the time taken for MemoryDB initialization
        end_time_redis = time.time()
        print(f"Vector store initialization time: {(end_time_redis - start_time_redis) * 1000:.2f} ms")
        # Start measuring time for retriever initialization
        start_time_retriever = time.time()
        # Get the retriever from the MemoryDB instance
        retriever = memorydb_client.as_retriever()
        # Measure and print the time taken for retriever initialization
        end_time_retriever = time.time()
        print(f"Retriever initialization time: {(end_time_retriever - start_time_retriever) * 1000:.2f} ms")
        return retriever
    except Exception as e:
        # Print the error message in case of an exception
        print(f"Error occurred during initialization: {e}")
        return None


def perform_query(query):
    results = memorydb_client.similarity_search(query)
    return results


# Initialize Retrieval QA with prompt
def query_and_get_response(question):
    system_prompt = (
        "Use the given context to answer the question. "
        "If you don't know the answer, say you don't know. "
        "Use three sentences maximum and keep the answer concise. "
        "Context: {context}"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )
    llm=get_llm()
    retriever=initializeRetriever()
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    chain = create_retrieval_chain(retriever, question_answer_chain)
    response = chain.invoke({"input": question})
    result=response["answer"]
    return result

    
def noContext(question):
    llm = get_llm()
    # Construct a prompt that instructs the LLM to provide concise answers
    concise_prompt = "Please provide a concise answer to the following question:\n\n"
    # Combine the concise instruction with the user's question
    full_question = concise_prompt + question
    try:
        # Generate a response using the LLM
        response_text = llm.invoke(full_question)  # Pass the combined prompt and question to the model
        result=response_text.content
        return result
    except Exception as e:
        # Handle any exceptions that occur during LLM prediction
        print(f"Error during LLM prediction: {e}")
        return None

memorydb_client = InMemoryVectorStore(
    redis_url = MEMORYDB_CLUSTER_URL,
    index_name = INDEX_NAME,
    embedding = initialize_embeddings(),
    # index_schema=index_schema  # Include the index schema if provided
)