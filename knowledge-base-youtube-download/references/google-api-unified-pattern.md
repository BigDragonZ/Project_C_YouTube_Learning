# Google API Unified Call Pattern (google-genai SDK)

All Google API operations (transcription, refinement, any future Gemini usage) MUST follow this pattern.

## Principle

Never hardcode a single endpoint. Always implement fault-tolerant backend chain:

1. **GCP Vertex AI first** — consumes project credits, preferred
2. **Gemini Standard API fallback** — standard API key, backup

## CRITICAL: Use google-genai SDK, NOT REST API

The user explicitly corrected: "应该通过 google-genai 去调用，gemini 也是". 

**Anti-pattern**: Hand-crafting urllib REST API calls. This was wrong because:
- Vertex AI and Gemini Standard API have different auth flows that the SDK handles automatically
- REST API requires different endpoint URLs, request body shapes, and error handling
- The SDK's `Client` class abstracts these differences

**Correct pattern**: Use `google.genai.Client` with appropriate initialization.

## Implementation

### Unified Client (lib/gemini_client.py)

```python
from google.genai import Client
from google.genai.types import GenerateContentConfig, HttpOptions, Part

# Vertex AI client
vertex_client = Client(
    vertexai=True,
    api_key=api_key,  # NOT project/location combo
    http_options=HttpOptions(api_version="v1"),
)

# Gemini Standard API client  
gemini_client = Client(api_key=api_key)
```

**Key insight**: Vertex AI with `api_key` parameter works; `project`+`location` without `api_key` fails for gemini-3.1-pro-preview with 404.

### Fault-Tolerant Generation

```python
def generate_content(contents, config=None, preferred_backend=None):
    cfg = load_config()
    backends = []
    if cfg.gcp_api_key:
        backends.append("gcp-vertex")
    if cfg.google_api_key:
        backends.append("gemini")
    
    for backend in backends:
        try:
            if backend == "gcp-vertex":
                client = Client(vertexai=True, api_key=cfg.gcp_api_key,
                              http_options=HttpOptions(api_version=cfg.api_version))
                response = client.models.generate_content(
                    model=cfg.gcp_model, contents=contents, config=config
                )
                return response.text
            else:
                client = Client(api_key=cfg.google_api_key)
                response = client.models.generate_content(
                    model=cfg.gemini_std_model, contents=contents, config=config
                )
                return response.text
        except Exception as e:
            print(f"[WARN] {backend} failed: {e}")
            continue
    raise RuntimeError("All backends failed")
```

### Audio Upload

```python
with open(audio_path, "rb") as f:
    audio_data = f.read()

contents = [
    "Transcribe this audio...",
    Part.from_bytes(data=audio_data, mime_type="audio/mpeg"),
]

text = generate_content(contents, config=GenerateContentConfig(
    temperature=0, max_output_tokens=8192
))
```

## Model Availability (as of 2026-05)

| Model | Vertex AI (api_key) | Vertex AI (project+location) | Gemini Standard API |
|-------|---------------------|------------------------------|---------------------|
| gemini-2.5-flash-lite | ✅ | ✅ | ✅ |
| gemini-2.5-pro | ✅ | ❌ 404 | ❓ |
| gemini-3.1-pro-preview | ✅ | ❌ 404 | ❌ 403 (key blocked) |

**Key finding**: `api_key` parameter is REQUIRED for Vertex AI to access newer models like gemini-3.1-pro-preview. Using `project`+`location` without `api_key` results in 404.

## Environment Variables

| Variable | Purpose | Required By |
|----------|---------|-------------|
| `gcp-vertex-key` | Vertex AI API key | Vertex AI backend |
| `GEMINI_API_KEY` | Standard Gemini API key | Gemini fallback |
| `TRANSCRIBER` | Explicit backend choice | Optional |
| `GCP_MODEL` | Vertex AI model name | Optional |
| `GEMINI_STD_MODEL` | Gemini fallback model | Optional |

## Anti-Patterns

❌ Hand-crafting urllib REST API calls  
❌ Using `Client(vertexai=True, project=..., location=...)` without `api_key` for newer models  
❌ Hardcoding single endpoint  
❌ Not handling 404/403 as retry signals  

## See Also

- `references/model-availability-2026-05.md` — detailed model status
- `lib/gemini_client.py` — working unified client implementation
- `lib/transcribe.py` — transcription using unified client
- `lib/refine.py` — refinement using unified client
