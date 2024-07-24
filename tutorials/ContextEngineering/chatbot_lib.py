import os
import redis
from redis.cluster import RedisCluster
import json
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
INDEX_NAME = 'idx:vss-chatbot'
MEMORYDB_CLUSTER_URL = f"rediss://{MEMORYDB_CLUSTER}:6379/ssl=True&ssl_cert_reqs=none"
pdf_path= "policy_doc.pdf"
rc = MemoryDBCluster(host=MEMORYDB_CLUSTER, port=6379, ssl=True, decode_responses=True, ssl_cert_reqs="none")
def initialize_memorydb():
    configs = get_configs()
    
    client = MemoryDBCluster(
        host=configs['MEMORYDB_CLUSTER'], 
        port=6379,
        ssl=True, 
        decode_responses=True, 
        ssl_cert_reqs="none"
    )
    try:
        client.ping()
        print("Connection to MemoryDB successful")
        return client
    except Exception as e:
        print("An error occurred while connecting to Redis:", e)
        return None

def get_configs():
    configs = {}
    configs['MEMORYDB_CLUSTER'] = os.environ.get("MEMORYDB_CLUSTER")
    return configs

# Initialize Bedrock model
def get_llm():
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
    return BedrockEmbeddings()

def check_index_existence():
    try:
        client = initialize_memorydb()
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
    start_time = time.time()
    embeddings = initialize_embeddings()
    try:
        loader = PyPDFLoader(file_path=pdf_path)
        pages = loader.load_and_split()
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", " "],
            chunk_size=500,
            chunk_overlap=50
        )
        chunks = loader.load_and_split(text_splitter)
        vectorstore = InMemoryVectorStore.from_documents(
            chunks,
            embedding=embeddings,
            redis_url=MEMORYDB_CLUSTER_URL,
            index_name=INDEX_NAME,
        )
        end_time = time.time()
        
        with open('sampledata.txt', 'r') as file:
            data = json.load(file)
        for entry in data:
            try:
                user_id = entry['userId']
                purchase_data = {k: v for k, v in entry.items() if k != 'userId'}
                rc.hset(user_id, mapping=purchase_data)
            except KeyError as e:
                print(f"Missing key {e} in entry: {entry}")

        print("Data loaded into Redis successfully.")
        print(f"initializeVectorStore() executed in {end_time - start_time:.2f} seconds")
        return vectorstore
    except Exception as e:
        end_time = time.time()
        print(f"Error occurred during initializeVectorStore(): {e}")
        print(f"Failed execution time: {end_time - start_time:.2f} seconds")
        return None

def initializeRetriever():
    """
    Initializes a MemoryDB instance as a retriever for an existing vector store.
 
    :param redis_url: The URL of the MemoryDB cluster instance.
    :param index_name: The name of the index in the MemoryDB vector store.
    :param embeddings: The embeddings to use for the retriever.
    :param index_schema: (Optional) The index schema, if needed.
    :return: The retriever object or None in case of an error.
    """
    index_name = INDEX_NAME
    redis_url = MEMORYDB_CLUSTER_URL
    embeddings = initialize_embeddings()
    try:
        start_time_redis = time.time()
        end_time_redis = time.time()
        print(f"Vector store initialization time: {(end_time_redis - start_time_redis) * 1000:.2f} ms")

        # Load user data from 'sampledata.txt' into Redis
        with open('sampledata.txt', 'r') as file:
            data = json.load(file)
        for entry in data:
            try:
                user_id = entry['userId']
                purchase_data = {k: v for k, v in entry.items() if k != 'userId'}
                rc.hset(user_id, mapping=purchase_data)
            except KeyError as e:
                print(f"Missing key {e} in entry: {entry}")

        print("Data loaded into Redis successfully.")

        start_time_retriever = time.time()
        retriever = memorydb_client.as_retriever()
        end_time_retriever = time.time()
        print(f"Retriever initialization time: {(end_time_retriever - start_time_retriever) * 1000:.2f} ms")
        return retriever
    except Exception as e:
        print(f"Error occurred during initialization: {e}")
        return None

def perform_query(query):
    results = memorydb_client.similarity_search(query)
    return results

def fetch_user_data(rc, user_id):
    user_data = rc.hgetall(user_id)
    if user_data:
        user_data = {k: json.loads(v) if k == b"purchaseHistory" else v for k, v in user_data.items()}
    return user_data

def askmeanything(question, user_details):
    llm = get_llm()
    similarity_response = perform_query(question)
    concise_prompt = "human: assume yourself as customer care agent talking to customer over chat: Use the following pieces of context to provide a concise answer in English to the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer. also do not answer anything which is out of context do not use your wider knowledge to makeup the answer\n\n"
    contextMemDB = fetch_user_data(rc, user_details)
    print(contextMemDB)
    if isinstance(similarity_response, list):
        similarity_response = '. '.join(map(str, similarity_response))
    elif not isinstance(similarity_response, str):
        similarity_response = str(similarity_response)

    if isinstance(contextMemDB, list):
        contextMemDB = '. '.join(map(str, contextMemDB))
    elif not isinstance(contextMemDB, str):
        contextMemDB = str(contextMemDB)

    full_question = (concise_prompt +
                     " use context of company policy matching customer product policy:" + similarity_response +
                     " match policy with customer product before responding. Use the following customer purchase history and dates:{ \n\n " +
                     contextMemDB) + "}following is the question of the user which you need to answer \n\n question:" + question +"? Assistant:"

    try:
        response_text = llm.invoke(full_question)
        result = response_text.content
        return result
    except Exception as e:
        print(f"Error during LLM prediction: {e}")
        return None

memorydb_client = InMemoryVectorStore(
    redis_url = MEMORYDB_CLUSTER_URL,
    index_name = INDEX_NAME,
    embedding = initialize_embeddings(),
)
