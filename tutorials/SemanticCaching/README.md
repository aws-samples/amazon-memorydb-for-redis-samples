# Amazon MemoryDB for Valkey
## Semantic Caching with Amazon MemoryDB. 

With the growth of generative artificial intelligence (AI), more organizations are running proofs of concept or small-scale production applications. However, as these organizations move into large-scale production deployments, costs and performance become primary concerns. To address these concerns, customers would typically turn to traditional caches to control costs on read-heavy workloads. However, in generative AI, part of the difficulty revolves around the ability for applications, such as chatbots, to cache the natural language requests they accept as inputs, given the variations in which inputs can be framed.

With the launch of vector search for Amazon MemoryDB, you can use MemoryDB, an in-memory database with Multi-AZ durability, as a persistent semantic caching layer. Semantic caching can improve the performance of generative AI applications by storing responses based on the semantic meaning or context within the queries.

Specifically, you can store the vector embeddings of requests and the generated responses in MemoryDB, and you can search for similarity between vectors instead of an exact match. This approach can reduce the response latency from seconds to single-digit milliseconds, and decrease costs in compute and requests to additional vector databases and foundation models (FMs), making your generative AI applications a reality from a cost and performance basis.

In this tutorial, we will use an in-memory database, Amazon MemoryDB, to demonstrate this pattern.


## Requirements
- Jupyter Lab
- MemoryDB with Vector Search enabled

## Getting Started
Open Jupyter Notebook `DurableSCwithFilter.ipynb`

## Security
See   [CONTRIBUTING](CONTRIBUTING.md) for more information.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

Author: Lakshmi Peri <lvperi@amazon.com>


## License
This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE.md) file.

