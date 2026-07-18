# Troubleshooting

## Backend Issues

| Error | Cause | Solution |
|-------|-------|----------|
| Backend won't start | Port 8000 in use | Kill process on port 8000 or change port in config |
| "ModuleNotFoundError" | Missing dependency | Run `uv sync` |
| Database errors | Corrupt DB | Delete `backend/data/veyron.db` and restart |
| CORS errors | Wrong origin | Ensure frontend is on allowed origin (5173 for dev) |

## Ollama Issues

| Error | Cause | Solution |
|-------|-------|----------|
| Connection refused | Ollama not running | Start Ollama, verify at http://localhost:11434 |
| Model not found | Model not pulled | `ollama pull qwen2.5:3b-instruct` |
| Slow responses | Wrong model size | Use 3B parameter model for development |
| Out of memory | Model too large for RAM | Use smaller quantized model |

## Frontend Issues

| Error | Cause | Solution |
|-------|-------|----------|
| Blank page | Build error | Check browser console, rebuild with `npm run build` |
| Can't connect to backend | Backend not running | Start backend first, check port |
| WebSocket disconnects | Backend restart | Auto-reconnect implemented (up to 30s backoff) |
| Stale data | Cache | Hard refresh (Ctrl+F5) |

## Tauri Desktop Issues

| Error | Cause | Solution |
|-------|-------|----------|
| Sidecar won't start | Binary not found | Rebuild with `npm run tauri:build` |
| "Backend not ready" timeout | Slow startup | Check `%TEMP%/veyron-diag.log` |
| Update fails | Network issue | Check GitHub Releases accessibility |
| Installer fails | Antivirus | Add exception for installer |

## General Debugging

- Check backend logs: `backend/data/veyron.log`
- Check Tauri diagnostics: Settings → Diagnostics page
- Check health endpoint: `curl http://localhost:8000/health`
- Reproduce in browser dev mode (`npm run dev`) for better error messages
