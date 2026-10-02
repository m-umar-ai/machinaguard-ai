# Deployment Guide

## 1. Put the project on GitHub
Before the first `git add`, make sure `.gitignore` contains `.env` and `.venv/` (the one in this project does).

```bash
git init
git add .
git ls-files | findstr /i "\.env venv"     # Mac/Linux: git ls-files | grep -E "\.env|venv"
```
The only match must be `.env.example`. If `.env` or any `.venv` file is listed, stop and fix `.gitignore`, then run `git rm -r --cached .` and `git add .` again.

```bash
git commit -m "MachinaGuard AI"
git branch -M main
git remote add origin https://github.com/<your-username>/machinaguard-ai.git
git push -u origin main
```
`.github/workflows/ci.yml` runs the tests on every push.

## 2. Streamlit Community Cloud (free)
1. Sign in at share.streamlit.io with GitHub and click **New app**.
2. Choose the repository, branch `main`, main file `app.py`.
3. **Advanced settings:** Python **3.12**. Under **Secrets** paste (with your own key and a model that passes `python final_check.py` on your computer):
```toml
   OPENAI_API_KEY = "your-key"
   OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
   OPENAI_MODEL = "qwen/qwen3.8-27b"
   OPENAI_FALLBACK_MODELS = "openai/gpt-oss-120b"
   LLM_PROVIDER = "openai"
```
4. Deploy. The first start retrains the small anomaly model, which takes a few seconds.
5. Put the public link at the top of the README.

## 3. Hugging Face Spaces (second platform)
1. Create a **Docker** Space (blank template).
2. Put this block at the very top of the Space's README:
```yaml
   ---
   title: MachinaGuard AI
   sdk: docker
   app_port: 7860
   ---
```
3. Push the same code to the Space and add the same keys under **Settings, Variables and secrets**.

The included `Dockerfile` also works on Render, Railway and Google Cloud Run.

## 4. Before you share the link
- Open the public URL and run **DEMO MODE** once from start to finish.
- With no key, the app runs in offline mode, which is fine for judging.
- Free AI tiers have rate limits. Avoid many repeated questions right before a presentation.
- Never put keys in the repository, the README or a screenshot.