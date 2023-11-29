# Langchain MemoryDB
This project provides a LangChain VectorStore class for working with [Amazon MemoryDB](https://aws.amazon.com/memorydb/) vector database.


## Installing the Package
To install the package, do the following:

1. git clone git@ssh.gitlab.aws.dev:langchain/langchain-memorydb.git    (NOTE: Needs to be updated once the project is moved to a public repo)
2. cd langchain-memorydb
3. pip install .   (NOTE: There is a DOT at the end.)


## Contributing to the Project
If you are a developer and would like to contribute to the project, run the following commands once after the repository is checked out.

1. Install pre-commit:
```shell
pip install pre-commit
```

2. Setup pre-commit:
```shell
pre-commit install
```

3. Install the project in editable mode:
```shell
pip install -e .
```

## Using MemoryDB VectorStore
To use the MemoryDB VectorStore, import the class MemoryDB:
```text
from langchain_memorydb import MemoryDB
```

Example 1:
```text
from langchain_memorydb import MemoryDB

vectorstore = MemoryDB.from_texts(
    texts,
    embeddings,
    metadatas = metadata,
    redis_url = REDIS_URL,
    index_name = INDEX_NAME,
)
```

Example 2:
```text
from langchain_memorydb import MemoryDB

vectorstore = MemoryDB.from_documents(
    documents,
    embeddings,
    redis_url = REDIS_URL,
    index_name = INDEX_NAME,
)
```

Example 3:
```text
from langchain_memorydb import MemoryDB
from langchain.embeddings import OpenAIEmbeddings

embeddings = OpenAIEmbeddings()
vectorstore = MemoryDB.from_existing_index(
    embeddings,
    index_name=INDEX_NAME,
    schema=None,
    redis_url=REDIS_URL,
)

query = "What is the company's strategy for generative AI?"
results = vectorstore.similarity_search(query)
```

The "samples" folder contains sample code written in python notebook.
