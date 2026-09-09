import httpx
from typing import List
from fastapi import HTTPException

from app.core.config import ollama_settings


async def generate_embedding(text: str) -> List[float]:
    url = f"{ollama_settings.OLLAMA_URL.rstrip('/')}/api/embeddings"
    payload = {
        "model": ollama_settings.OLLAMA_MODEL,
        "prompt": text
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            return data["embedding"]
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Ollama connection error: {str(e)}")