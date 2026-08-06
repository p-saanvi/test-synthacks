# Health 360

this is a test to see if 2 boys and 1 girl can solve the healthcare crisis

See [`memory.md`](./memory.md) for a full project overview (flow, data model,
and the AI hand-off API contract).

## Running locally

```bash
cd server
npm install
node server.js
```

The server starts at http://localhost:4000 and serves the website itself
(from `/public`) as well as the API. A `health360.db` SQLite file is created
automatically in `server/` the first time you run it — no extra setup needed.

Then open http://localhost:4000 in your browser and either **Create Account**
or **Sign In**.

## Project layout

- `server/` — Node.js + Express backend, SQLite database, and the API
  (auth, profile, emergency contacts, and the placeholder "AI slot" that
  hands data off to the hospital-search AI a teammate is building).
- `public/` — plain HTML/CSS/JS frontend pages (no framework).
