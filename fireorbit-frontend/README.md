# FireOrbit Frontend

AI-powered assistant UI for NASA combustion science research. React + TypeScript + Vite.
Works fully offline in **mock mode**; switches to the FastAPI backend with two env vars and no UI changes.

## Setup

```bash
cd frontend
npm install
cp .env.example .env     # then edit if needed
npm run dev              # http://localhost:5173
npm run build            # type-checks, then builds to dist/
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_USE_MOCK_API` | `true` (anything except `false`) | `true` = built-in mock API, no backend needed. `false` = call the real backend. |
| `VITE_API_BASE_URL` | `http://localhost:8000` | FastAPI base URL (live mode only). |

Restart the dev server after changing `.env`. The backend must allow CORS from the frontend origin
(e.g. `http://localhost:5173`) via FastAPI's `CORSMiddleware`.

## Mock mode

- Answers and sources are **placeholders**, labelled "Mock response" / "Mock" in the UI. They are not real research data.
- Canned topics: combustion instability, flame spread in microgravity, spherical/blue flames, oxygen & flammability, Saffire.
  Anything else returns a clearly labelled fallback.
- Include `/error` in a message to trigger the error state.
- Conversations persist in `localStorage` (clear them in Settings).

## Backend contract (PROPOSED, not confirmed)

| Endpoint | Request | Response |
| --- | --- | --- |
| `POST /api/chat` | `{ "question": string, "conversation_id": string \| null }` | `{ "answer": string, "conversation_id": string, "sources": [{ "document", "page", "chunk_id", "content" }] }` |
| `GET /api/conversations` | none | `[{ "id", "title", "updated_at" }]` (a `{ "conversations": [...] }` wrapper is also accepted) |
| `GET /api/conversations/{id}` | none | `{ "id", "title", "messages": [{ "role": "user" \| "assistant", "content", "sources?", "created_at?" }] }` |
| `GET /health` | none | any 2xx |

The list/detail shapes were not specified in the brief; they are my assumption. FastAPI error bodies
(`{ "detail": string | [{ "msg" }] }`) are shown to the user.

**Regenerate** re-sends the same question with the current `conversation_id`. The proposed contract has no
regenerate flag, so a real backend will append a second copy of that turn unless it de-duplicates or a flag is added.

## Structure

```
src/
  components/   Sidebar, ChatWindow, MessageBubble, MessageInput, SourceCitations,
                WelcomeScreen, SettingsModal, MarkdownContent, Logo, Icons
  pages/        ChatPage (composes everything)
  hooks/        useChat (all chat state/actions), useSettings, useHealth
  services/     api.ts (the ONLY mock/real switch), realApi.ts, httpClient.ts, config.ts
  mocks/        mockApi.ts (ChatApi implementation), mockData.ts (canned content)
  types/        shared TypeScript types incl. the ChatApi interface
  styles/       theme.css (tokens), app.css, markdown.css
```

To adapt to a different backend, edit only `services/realApi.ts` (paths, field names). Components depend on
the `ChatApi` interface in `types/`, never on a concrete implementation.
