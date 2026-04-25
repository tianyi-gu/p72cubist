"""FastAPI server for EngineLab.

Exposes the Python tournament backend as an HTTP API so the React frontend
can call it. Tournament progress is streamed via Server-Sent Events (SSE).

Run from project root:
    uvicorn api.server:app --reload --port 8000
"""

import asyncio
import dataclasses
import json
import threading
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from features.registry import get_feature_names, get_feature_description
from variants.base import get_supported_variants
from agents.generate_agents import generate_feature_subset_agents
from tournament.round_robin import run_round_robin
from tournament.leaderboard import compute_leaderboard
from analysis.feature_marginals import compute_feature_marginals
from analysis.synergy import compute_pairwise_synergies


app = FastAPI(title="EngineLab API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _variant_hints(feature_id: str) -> list[str]:
    """Return variant hints for a feature based on its name."""
    hints: list[str] = []
    if "antichess" in feature_id:
        hints.append("antichess")
    if "explosion" in feature_id:
        hints.append("atomic")
    return hints


def _display_name(feature_id: str) -> str:
    """Convert underscore feature id to title-case display name."""
    return feature_id.replace("_", " ").title()


def _leaderboard_to_dict(row) -> dict[str, Any]:
    """Serialize a LeaderboardRow dataclass to a JSON-safe dict."""
    d = dataclasses.asdict(row)
    d["features"] = list(d["features"])
    return d


def _marginal_to_dict(row) -> dict[str, Any]:
    """Serialize a FeatureContributionRow dataclass to a JSON-safe dict."""
    return dataclasses.asdict(row)


def _synergy_to_dict(row) -> dict[str, Any]:
    """Serialize a SynergyRow dataclass to a JSON-safe dict."""
    return dataclasses.asdict(row)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class TournamentRequest(BaseModel):
    variant: str = "atomic"
    feature_names: list[str]
    depth: int = 1
    max_moves: int = 60
    max_agents: int = 20
    seed: int = 42
    workers: int = 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/features")
async def features():
    """Return all registered features with display name, description, and variant hints."""
    names = get_feature_names()
    return {
        "features": [
            {
                "id": name,
                "name": _display_name(name),
                "description": get_feature_description(name),
                "variant_hints": _variant_hints(name),
            }
            for name in names
        ]
    }


@app.get("/api/variants")
async def variants():
    """Return all supported variant names."""
    return {"variants": get_supported_variants()}


@app.post("/api/tournament")
async def tournament(req: TournamentRequest):
    """Run a round-robin tournament and stream progress via SSE."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def run():
        try:
            agents = generate_feature_subset_agents(
                req.feature_names,
                max_agents=req.max_agents,
                seed=req.seed,
            )

            def on_game_complete(done: int, total: int, result) -> None:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "progress", "done": done, "total": total},
                )

            results = run_round_robin(
                agents=agents,
                variant=req.variant,
                depth=req.depth,
                max_moves=req.max_moves,
                seed=req.seed,
                on_game_complete=on_game_complete,
            )

            leaderboard = compute_leaderboard(results, agents)
            marginals = compute_feature_marginals(leaderboard, req.feature_names)
            synergies = compute_pairwise_synergies(leaderboard, req.feature_names)

            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "complete",
                    "leaderboard": [_leaderboard_to_dict(r) for r in leaderboard],
                    "marginals": [_marginal_to_dict(r) for r in marginals],
                    "synergies": [_synergy_to_dict(r) for r in synergies],
                },
            )
        except Exception as e:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "message": str(e)},
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    threading.Thread(target=run, daemon=True).start()

    async def generate():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
