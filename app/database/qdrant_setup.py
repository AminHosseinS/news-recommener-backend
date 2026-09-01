from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import VectorParams, Distance



async  def init_qdrant_collections(client: AsyncQdrantClient,recreate_if_exists: bool=False) :
    collection_name = "news_articles"
    vector_size = 768 # needs to be exact as embedding model

    if recreate_if_exists:
        await client.delete_collection(collection_name)
        print("dropped for recreation")

    exists = await  client.collection_exists(collection_name)

    if not exists:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
        print("created successfully")
    else:
        print("already exists")