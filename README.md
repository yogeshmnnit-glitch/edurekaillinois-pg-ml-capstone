# Multi-Agent Enterprise Knowledge Assistant

Capstone project: a Streamlit + LangGraph agentic RAG assistant that answers natural-language
questions over uploaded enterprise documents (PDF, Word, Excel, CSV, TXT), grounded in a ChromaDB
vector store of 3GPP/telecom content, with confidence-gated answers and a "please upload more
documents" recovery flow instead of fabricating responses.

## Status
Planning complete, implementation not yet started. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the
full design: requirements mapping, tech stack, 5-agent architecture, workflow triggers, chat
history/observability design, project structure, sequence & module diagrams, implementation
phases, and test plan.

## Repository layout (current)
- `Sample Data/` — optional local documents available for the user to select and upload manually; never indexed automatically
- `Input Data/<session_id>/` — documents uploaded in the current browser session (git-ignored)
- `ChromaKnowledgeBaseDB/` — vector store persistence directory (git-ignored)
- `Utility/storage/sessions/<session_id>.db` — session-scoped chat history and token usage (git-ignored)
- `UI Images/` — branding assets
- `Utility/` — application code: agents, graph, ingestion, vectorstore, llm, storage, metrics, config, ui
- `app.py` — Streamlit entrypoint (added in a later phase)
- `.env` / `.env.example` — configuration (API keys, models, thresholds); `.env` is git-ignored
- `requirements.txt` — Python dependencies
- `activate_env.bat` / `create_venv.bat` / `deactivate_env.bat` — local Python virtual environment helpers

Each Streamlit browser session receives a unique session ID. Uploaded files, Chroma collections,
chat history, and token metrics are isolated by that ID. A new user starts with an empty document
list and must upload documents before asking questions.

## Getting started
1. `create_venv.bat` then `activate_env.bat`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`
4. Run instructions (`streamlit run app.py`) will be added once `app.py` exists
5. Upload documents form `./Sample Data`. You can upload one or many of different type of documents.
6. As this is Telecom  research specific docuemnts. There are sample questions from one or more documents listed in `"Bot Sample Questions.md"`.   