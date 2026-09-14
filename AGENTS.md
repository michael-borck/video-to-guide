# Working agreements

- Commit and push to GitHub at the end of every work batch, without asking.
- Python venv lives off-repo: `export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/video-to-guide"`
  (project sits on exFAT, which breaks venvs). The same volume produces
  AppleDouble `._*` files everywhere; they are gitignored, never commit them.
- Frontend changes require `npm run build` in `frontend/` before the FastAPI
  server serves them; `npm run dev` gives hot reload against the API.
- Before killing/restarting uvicorn, `pkill -f "uvicorn backend.main"` — a
  stale process silently answers old routes.
- PyPI distribution and module name is `videotoguide`; repo/project name is
  `video-to-guide`. Do not publish until the naming decision is revisited.
