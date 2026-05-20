# Security Notice

**IMPORTANT:**
Previous commits in this repository's history may have contained exposed API keys in `backend/.env`.

If you have cloned or forked this repository and your live API keys were inadvertently committed, you must **ROTATE YOUR KEYS IMMEDIATELY** in your provider dashboard (e.g., OpenWeatherMap, Google Gemini).

Going forward:
- The `backend/.env` file is now included in `.gitignore` and will no longer be tracked.
- Use `backend/.env.example` as a template for setting up your local environment.
