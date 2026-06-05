#!/usr/bin/env python3
"""
Test transcription backend availability.
Usage: python3 test_transcription_backend.py
"""

import os
from google.genai import Client
from google.genai.types import GenerateContentConfig, HttpOptions

API_KEY = os.environ.get("gcp-vertex-key", "")


def test_vertex(model: str) -> bool:
    try:
        client = Client(vertexai=True, api_key=API_KEY, http_options=HttpOptions(api_version="v1"))
        response = client.models.generate_content(
            model=model,
            contents="Say hi",
            config=GenerateContentConfig(temperature=0, max_output_tokens=500),
        )
        if response.text:
            print(f"  ✅ Vertex {model}: OK ({response.text[:30]}...)")
            return True
        print(f"  ⚠️  Vertex {model}: empty response")
        return False
    except Exception as e:
        print(f"  ❌ Vertex {model}: {type(e).__name__}: {str(e)[:100]}")
        return False


def test_gemini(model: str) -> bool:
    try:
        client = Client(api_key=API_KEY)
        response = client.models.generate_content(
            model=model,
            contents="Say hi",
            config=GenerateContentConfig(temperature=0, max_output_tokens=500),
        )
        if response.text:
            print(f"  ✅ Gemini {model}: OK ({response.text[:30]}...)")
            return True
        print(f"  ⚠️  Gemini {model}: empty response")
        return False
    except Exception as e:
        print(f"  ❌ Gemini {model}: {type(e).__name__}: {str(e)[:100]}")
        return False


if __name__ == "__main__":
    print("Testing Google API backends...")
    print(f"API key: {API_KEY[:20]}...")
    print()

    print("Vertex AI backends:")
    for m in ["gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-3.1-pro-preview"]:
        test_vertex(m)

    print()
    print("Gemini Standard API backends:")
    for m in ["gemini-2.5-flash-lite"]:
        test_gemini(m)
