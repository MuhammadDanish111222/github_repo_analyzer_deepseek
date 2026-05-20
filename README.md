---
title: GitHub Repo Analyzer DeepSeek
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Live GitHub Repository Analyzer API

FastAPI backend service that accepts a public GitHub repository URL, fetches the primary source code file, analyzes it using DeepSeek, and returns a structured vulnerability report.

## Tech Stack

- Python 3.11.9
- FastAPI
- DeepSeek Chat Completions API
- GitHub REST API
- Docker
- Hugging Face Spaces free CPU deployment

## Endpoint

```http
POST /api/analyze-repo
```

Request body:

```json
{
  "repo_url": "https://github.com/username/repository"
}
```

Response body:

```json
{
  "status": "success",
  "repo_name": "repository-name",
  "vulnerabilities_found": [
    "Description of bug/vulnerability 1",
    "Description of bug/vulnerability 2"
  ],
  "suggestions": "Brief structural or optimization advice."
}
```

## Local Setup

Create virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Add your DeepSeek API key:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

Run locally:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open docs:

```text
http://localhost:8000/docs
```

## Hugging Face Spaces Deployment

1. Create a free Hugging Face account.
2. Go to Spaces.
3. Click **Create new Space**.
4. Use this setup:
   - Space name: `github-repo-analyzer-deepseek`
   - SDK: `Docker`
   - Visibility: `Public`
   - Hardware: `CPU basic free`
5. Upload all project files to the Space repository.
6. Go to **Settings > Variables and secrets**.
7. Add these Secrets:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

8. Add these Variables:

```env
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING_TYPE=enabled
DEEPSEEK_REASONING_EFFORT=high
APP_ENV=production
REQUEST_TIMEOUT_SECONDS=60
MAX_SOURCE_FILE_BYTES=200000
MAX_CODE_CHARS_FOR_LLM=80000
LOG_LEVEL=INFO
ALLOWED_ORIGINS=
PORT=7860
```

Optional Secret for higher GitHub API rate limits:

```env
GITHUB_TOKEN=your_github_token_here
```

After build completes, your API docs will be available at:

```text
https://YOUR_USERNAME-github-repo-analyzer-deepseek.hf.space/docs
```

Your assessment endpoint will be:

```text
https://YOUR_USERNAME-github-repo-analyzer-deepseek.hf.space/api/analyze-repo
```

## Test Live API

```bash
curl -X POST "https://YOUR_USERNAME-github-repo-analyzer-deepseek.hf.space/api/analyze-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/tiangolo/fastapi"}'
```

## Security Notes

- Do not commit `.env`.
- Store `DEEPSEEK_API_KEY` as a Hugging Face Secret.
- Store `GITHUB_TOKEN` as a Secret if used.
- Only `.env.example` should be public.
