# GCP Vertex AI / Gemini Transcription via REST API

## Problem

The `google-genai` Python SDK has initialization conflicts when combining `vertexai=True` with `api_key`:

```
ValueError: Project/location and API key are mutually exclusive in the client initializer.
```

Additionally, model names like `gemini-3.1-pro-preview` return 404 on Vertex AI endpoints.

## Solution: Direct REST API Calls

Bypass the SDK client entirely. Use Python's `urllib.request` with inline base64 audio.

### Vertex AI Endpoint

```python
import urllib.request
import json
import base64
import os

api_key = os.environ.get('gcp-vertex-key', '')
audio_path = 'path/to/audio.mp3'

with open(audio_path, 'rb') as f:
    audio_b64 = base64.b64encode(f.read()).decode()

url = (
    'https://us-central1-aiplatform.googleapis.com/v1/'
    'projects/gen-lang-client-0385617544/locations/us-central1/'
    'publishers/google/models/gemini-2.5-flash-lite:generateContent'
    f'?key={api_key}'
)

data = {
    'contents': [{
        'role': 'user',
        'parts': [
            {'text': 'Transcribe this audio accurately.'},
            {'inline_data': {'mime_type': 'audio/mpeg', 'data': audio_b64}}
        ]
    }],
    'generationConfig': {'temperature': 0, 'maxOutputTokens': 8192}
}

req = urllib.request.Request(
    url,
    data=json.dumps(data).encode(),
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
text = result['candidates'][0]['content']['parts'][0]['text']
```

### Gemini Standard Endpoint

```python
url = (
    'https://generativelanguage.googleapis.com/v1beta/'
    f'models/gemini-2.5-flash-lite:generateContent?key={api_key}'
)
# Same data structure as Vertex
```

## Key Differences

| Aspect | Vertex AI | Gemini Standard |
|--------|-----------|-----------------|
| URL base | `{location}-aiplatform.googleapis.com` | `generativelanguage.googleapis.com` |
| Path | `/v1/projects/{project}/locations/{location}/publishers/google/models/{model}` | `/v1beta/models/{model}` |
| Auth | API key in query param | API key in query param |
| Audio | inline_data (base64) | inline_data (base64) |
| Max tokens | 8192 | 8192 |

## Working Vertex Models (as of 2026-05)

- `gemini-2.5-flash-lite` ✅
- `gemini-3.1-pro-preview` ❌ (404)
- `gemini-1.5-pro` ❌ (404)
- `gemini-1.5-flash` ❌ (404)

## Fault-Tolerant Chain

1. Try Vertex AI with `gcp-vertex-key` first (uses project credits)
2. Fallback to Gemini Standard with `GEMINI_API_KEY`
3. Both use identical request body structure

## Pitfall: GCS URI vs Inline Data

The SDK's `Part.from_uri()` requires GCS upload first. With REST API, use `inline_data` with base64 to skip GCS entirely — faster and simpler for small-to-medium audio files (< 20MB).

## Pitfall: Environment Variable Names

- `gcp-vertex-key` (lowercase with hyphens) for Vertex AI
- `GEMINI_API_KEY` (uppercase with underscores) for standard API
- Both stored in user's `.env` or shell profile
