# Gemini Model Availability (2026-05)

## Vertex AI Endpoint

Base URL pattern: `https://{location}-aiplatform.googleapis.com/v1/...`

### With api_key parameter (google-genai SDK)

| Model | Status | Notes |
|-------|--------|-------|
| gemini-2.5-flash-lite | ✅ Working | Default transcription model |
| gemini-2.5-pro | ✅ Working | Default refinement model |
| gemini-3.1-pro-preview | ✅ Working | Requires api_key, NOT project+location |

### With project+location only (no api_key)

| Model | Status | Notes |
|-------|--------|-------|
| gemini-2.5-flash-lite | ✅ Working | |
| gemini-2.5-pro | ❌ 404 | Not accessible |
| gemini-3.1-pro-preview | ❌ 404 | Not accessible |

**Critical**: Newer models (gemini-3.1-pro-preview, gemini-2.5-pro) require `api_key` parameter on Vertex AI. Using only `project`+`location` results in 404.

## Gemini Standard API

Base URL: `https://generativelanguage.googleapis.com/v1beta/...`

| Model | Status | Notes |
|-------|--------|-------|
| gemini-2.5-flash-lite | ✅ Working | Fallback option |
| gemini-3.1-pro-preview | ❌ 403 | Forbidden with current gcp-vertex-key |

## Key Finding

The `gcp-vertex-key` works for Vertex AI endpoints but returns 403 on Gemini Standard API. The `GEMINI_API_KEY` (if set) would be needed for standard API fallback.

For refinement tasks requiring highest quality, use `gemini-3.1-pro-preview` on Vertex AI with `api_key` parameter.

## Correct Client Initialization

```python
from google.genai import Client
from google.genai.types import HttpOptions

# Vertex AI with api_key — REQUIRED for gemini-3.1-pro-preview
client = Client(
    vertexai=True,
    api_key=api_key,
    http_options=HttpOptions(api_version="v1"),
)

# Vertex AI with project/location — ONLY works for older models
client = Client(
    vertexai=True,
    project=project_id,
    location=location,
    http_options=HttpOptions(api_version="v1"),
)

# Gemini Standard API
client = Client(api_key=api_key)
```
