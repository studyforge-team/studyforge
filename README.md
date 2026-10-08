# StudyForge

A study agent for engineering students that can't make up numbers. Nemotron (via Nebius
Token Factory) plans and writes Python, a sealed sandbox inside the app computes, and the
answer is checked and explained step by step with plots and diagrams. Around that, the agent
tracks deadlines (Telegram + uploads), builds a prep pack and quiz before each one, remembers
weak topics, and answers beyond-syllabus doubts with cited sources. ChemLab adds chemical-
engineering simulations (reactors, distillation, heat exchangers) with 3D models and
engineering drawings.

**Status: work in progress, hackathon build** (Nebius x NVIDIA Global AI Hackathon, Track 2).
The full README (setup, demo mode, architecture, licences) is coming with ticket F4.

## Folder map

- `api/` FastAPI backend (agent loop, routers, tests)
- `web/` React + Vite + TypeScript frontend, Pyodide sandbox, ChemLab screens
- `chemlab/` simulation templates in plain Python, with tests
- `runner/` Node Pyodide runner for CI and evals
- `config/` model registry and settings
- `docs/` architecture, decisions, feedback log

Contributors and AI assistants: see [AGENTS.md](AGENTS.md).

Licensed under the MIT License.
