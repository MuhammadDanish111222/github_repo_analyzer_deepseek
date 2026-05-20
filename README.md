# Live GitHub Repository Analyzer API

A production-ready FastAPI backend that accepts a public GitHub repository URL, fetches the most relevant primary source code file, analyzes it with DeepSeek, and returns a clean JSON security review.

## Tech stack

- Python 3.11.9
- FastAPI
- DeepSeek Chat Completions API
- httpx async HTTP client
- Pydantic v2 settings and validation
- Docker deployment, ready for Render free tier

## API contract

### POST `/api/analyze-repo`

Request:

```json
{
  "repo_url": "https://github.com/username/repository"
}
```

Response:

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

## Local setup

### 1. Install Python 3.11.9

Recommended on Windows:

```powershell
py -3.11 --version
```

Recommended on macOS/Linux with pyenv:

```bash
pyenv install 3.11.9
pyenv local 3.11.9
python --version
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create `.env`

Copy the example file:

```bash
cp .env.example .env
```

Then add your real DeepSeek key:

```env
DEEPSEEK_API_KEY=sk-your-real-key-here
```

Optional GitHub token is recommended to avoid low public API rate limits:

```env
GITHUB_TOKEN=github_pat_your_optional_token
```

### 5. Run locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/docs
```

### 6. Test the endpoint

```bash
curl -X POST "http://localhost:8000/api/analyze-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/tiangolo/fastapi"}'
```

## Docker run locally

```bash
docker build -t github-repo-analyzer .
docker run --rm -p 8000:10000 --env-file .env github-repo-analyzer
```

Then call:

```bash
curl -X POST "http://localhost:8000/api/analyze-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/tiangolo/fastapi"}'
```

## Deploy free on Render

1. Push this folder to a public GitHub repository.
2. Go to Render Dashboard.
3. Click **New**.
4. Choose **Web Service**.
5. Connect your GitHub repository.
6. Select **Docker** as the runtime or let Render detect the `Dockerfile`.
7. Choose the **Free** instance type.
8. Add environment variables:
   - `DEEPSEEK_API_KEY`
   - `DEEPSEEK_MODEL=deepseek-v4-flash`
   - `DEEPSEEK_BASE_URL=https://api.deepseek.com`
   - Optional: `GITHUB_TOKEN`
9. Deploy.

Your live endpoint will be:

```text
https://your-render-service.onrender.com/api/analyze-repo
```

Test it:

```bash
curl -X POST "https://your-render-service.onrender.com/api/analyze-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/tiangolo/fastapi"}'
```

## Project structure

```text
.
├── app
│   ├── core
│   │   └── config.py
│   ├── services
│   │   ├── deepseek_service.py
│   │   └── github_service.py
│   ├── __init__.py
│   ├── exceptions.py
│   ├── main.py
│   └── schemas.py
├── tests
│   ├── test_github_url_parser.py
│   └── test_primary_file_selection.py
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── render.yaml
└── requirements.txt
```

## Notes

- API keys are read only from environment variables.
- The service never stores repository code.
- The app analyzes one primary source file, as required by the assessment.
- The primary file selector prioritizes common application entry points such as `main.py`, `app.py`, `server.js`, `index.ts`, and similar files.
- Very large files are skipped to protect API limits and latency.
- Render free services can sleep after idle time, so the first request after inactivity can be slower.
