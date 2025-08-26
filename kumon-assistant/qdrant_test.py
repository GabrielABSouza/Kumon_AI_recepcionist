import os

from qdrant_client import QdrantClient


def main():
    host = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not host or not api_key:
        raise ValueError("Variáveis QDRANT_HOST e QDRANT_API_KEY não definidas!")

    client = QdrantClient(url=host, api_key=api_key)

    collections = client.get_collections()
    print("Collections disponíveis:", collections)


if __name__ == "__main__":
    main()
