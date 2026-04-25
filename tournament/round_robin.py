"""Round-robin tournament for EngineLab.

Plays every ordered pair (A as white, B as black) once.
N agents produce N*(N-1) games.
"""

import os
from concurrent.futures import ProcessPoolExecutor

from tqdm import tqdm

from agents.feature_subset_agent import FeatureSubsetAgent
from simulation.game import GameResult, play_game


def _run_game(args: tuple) -> GameResult:
    """Top-level worker — must be module-level for multiprocessing pickle."""
    white, black, game_seed, variant, depth, max_moves = args
    return play_game(white, black, variant=variant, depth=depth,
                     max_moves=max_moves, seed=game_seed)


def run_round_robin(
    agents: list[FeatureSubsetAgent],
    variant: str,
    depth: int,
    max_moves: int,
    seed: int,
    on_game_complete=None,
    max_workers: int | None = None,
) -> list[GameResult]:
    """Play every ordered pair once: N*(N-1) games.

    Per-game seed = tournament_seed + game_index for reproducibility.

    When on_game_complete is provided, runs sequentially (required for UI
    live updates). Otherwise uses ProcessPoolExecutor across all CPU cores.

    Args:
        on_game_complete: Optional callback(games_done, total, result).
            Triggers sequential mode for UI compatibility.
        max_workers: Worker processes for parallel mode. None = os.cpu_count().
    """
    game_args: list[tuple] = []
    game_index = 0
    for i, white in enumerate(agents):
        for j, black in enumerate(agents):
            if i == j:
                continue
            game_args.append((white, black, seed + game_index, variant, depth, max_moves))
            game_index += 1

    total = len(game_args)

    # Sequential mode: required when a live-update callback is provided (e.g. UI)
    if on_game_complete is not None:
        results: list[GameResult] = []
        for args in tqdm(game_args, desc="Tournament"):
            result = _run_game(args)
            results.append(result)
            on_game_complete(len(results), total, result)
        return results

    # Parallel mode: saturate CPU cores, order preserved by executor.map
    workers = max_workers if max_workers is not None else os.cpu_count()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(
            tqdm(executor.map(_run_game, game_args), total=total, desc="Tournament")
        )
    return results
