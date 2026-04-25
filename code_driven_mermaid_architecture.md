# Code-Driven Mermaid Architecture — p72cubist-main-2

This document is based on the actual Python source files in the uploaded project, not the Markdown docs.

Important correction: this project does **not** contain a separate React frontend, REST API backend, database server, or HTTP service layer. The "frontend" is `ui/app.py` running in Streamlit. It directly imports and calls Python modules from `agents`, `tournament`, `analysis`, `reports`, `features`, and `ui`. The CLI entrypoint is `main.py`. Both UI and CLI share the same engine/simulation/analysis backend code.

Source files walked:
- Frontend/UI: `ui/app.py`, `ui/board.py`, `ui/chess_viewer.py`, `ui/play_engine.py`, `ui/constants.py`
- Backend/domain: `core/*`, `variants/*`, `agents/*`, `search/alpha_beta.py`, `simulation/*`, `tournament/*`, `analysis/*`, `features/*`, `reports/markdown_report.py`, `export_data.py`
- CLI: `main.py`
- Persisted outputs: `outputs/data/*.json`, `outputs/data/*.csv`, `outputs/reports/*.md`

---

# 1. Frontend Architecture — Streamlit UI Layer

## 1.1 Frontend C4 Model

```mermaid
C4Context
    title Frontend C4 Context - Streamlit UI

    Person(user, "User", "Configures tournaments, views analysis, plays against engine")
    System_Boundary(frontend, "Frontend Boundary: Streamlit UI") {
        Container(streamlit_app, "ui/app.py", "Streamlit", "Main UI entrypoint and page orchestration")
        Container(board_renderer, "ui/board.py", "python-chess + chess.svg", "Renders board SVG from FEN and move highlights")
        Container(chess_viewer, "ui/chess_viewer.py", "Streamlit Components + HTML/JS", "Interactive game viewer and play board widgets")
        Container(play_adapter, "ui/play_engine.py", "Python adapter", "Converts UI FEN/SAN/UCI interaction into engine calls")
        Container(constants, "ui/constants.py", "Python constants", "Feature labels, variant descriptions, session defaults")
    }

    System_Ext(engine_backend, "Backend Python Modules", "agents, tournament, analysis, reports, search, core, variants")
    System_Ext(output_files, "Output Files", "JSON/CSV/Markdown in outputs/")

    Rel(user, streamlit_app, "Uses browser UI")
    Rel(streamlit_app, constants, "Reads UI labels/defaults")
    Rel(streamlit_app, board_renderer, "Renders static board")
    Rel(streamlit_app, chess_viewer, "Embeds interactive viewer/play component")
    Rel(streamlit_app, play_adapter, "Requests engine move for play panel")
    Rel(streamlit_app, engine_backend, "Direct Python imports/calls")
    Rel(streamlit_app, output_files, "Loads/saves tournament results and reports")
```

## 1.2 Frontend Component Diagram

```mermaid
flowchart TB
    subgraph UI["Frontend/UI package"]
        APP["ui/app.py<br/>main(), render panels, session state"]
        CONST["ui/constants.py<br/>ALL_FEATURES<br/>FEATURE_DISPLAY_NAMES<br/>SESSION_DEFAULTS<br/>VARIANT_DESCRIPTIONS"]
        BOARD["ui/board.py<br/>render_board()<br/>starting_fen()"]
        VIEWER["ui/chess_viewer.py<br/>chess_game_viewer()<br/>chess_play_interactive()<br/>chess_play_board()"]
        PLAY["ui/play_engine.py<br/>engine_reply()<br/>apply_san_move()<br/>game_status()"]
    end

    subgraph ImportedBackend["Direct backend imports used by ui/app.py"]
        FSA["agents.feature_subset_agent.FeatureSubsetAgent"]
        GEN["agents.generate_agents.generate_feature_subset_agents()"]
        RR["tournament.round_robin.run_round_robin()"]
        LB["tournament.leaderboard.compute_leaderboard()"]
        RIO["tournament.results_io<br/>load_results_json()<br/>save_results_json()"]
        FM["analysis.feature_marginals.compute_feature_marginals()"]
        SYN["analysis.synergy.compute_pairwise_synergies()"]
        INT["analysis.interpretation.generate_interpretation()"]
        REP["reports.markdown_report.generate_markdown_report()"]
        REG["features.registry.get_feature_names()"]
    end

    APP --> CONST
    APP --> BOARD
    APP --> VIEWER
    APP --> PLAY
    APP --> FSA
    APP --> GEN
    APP --> RR
    APP --> LB
    APP --> RIO
    APP --> FM
    APP --> SYN
    APP --> INT
    APP --> REP
    APP --> REG

    PLAY --> COREBOARD["core.board.Board.from_fen()"]
    PLAY --> FSA2["FeatureSubsetAgent"]
    PLAY --> ABE["search.alpha_beta.AlphaBetaEngine"]
    BOARD --> PYCHESS["python-chess / chess.svg"]
    VIEWER --> COMP["streamlit.components.v1.components.html()"]
```

## 1.3 Frontend Deployment Diagram

```mermaid
flowchart LR
    Browser["User Browser"]
    subgraph LocalMachine["Local Machine / Streamlit Runtime"]
        Streamlit["streamlit run ui/app.py"]
        PythonProcess["Single Python Process"]
        UIPackage["ui package"]
        BackendPackages["Imported backend packages<br/>agents/tournament/analysis/reports/core/search/variants/features"]
        FileSystem["Local filesystem<br/>outputs/data<br/>outputs/reports"]
    end

    Browser <-->|HTTP served by Streamlit| Streamlit
    Streamlit --> PythonProcess
    PythonProcess --> UIPackage
    PythonProcess --> BackendPackages
    PythonProcess <-->|read/write JSON/Markdown| FileSystem
```

## 1.4 Frontend Sequence Diagram — Start Tournament from UI

```mermaid
sequenceDiagram
    actor User
    participant APP as ui/app.py
    participant GEN as generate_feature_subset_agents()
    participant TH as threading.Thread
    participant RR as run_round_robin()
    participant RIO as save_results_json()
    participant ANA as _analyze_results()
    participant LB as compute_leaderboard()
    participant FM as compute_feature_marginals()
    participant SYN as compute_pairwise_synergies()
    participant INT as generate_interpretation()
    participant REP as generate_markdown_report()

    User->>APP: Click Start Tournament
    APP->>APP: _start_tournament()
    APP->>GEN: generate_feature_subset_agents(features, ...)
    GEN-->>APP: list[FeatureSubsetAgent]
    APP->>TH: start _run_tournament_thread(config)
    TH->>RR: run_round_robin(agents, ...)
    RR-->>TH: list[GameResult]
    TH->>RIO: save_results_json(results, path)
    TH->>ANA: _analyze_results(results, features, variant, config)
    ANA->>LB: compute_leaderboard(results, agents)
    LB-->>ANA: list[LeaderboardRow]
    ANA->>FM: compute_feature_marginals(leaderboard, features)
    FM-->>ANA: list[FeatureContributionRow]
    ANA->>SYN: compute_pairwise_synergies(leaderboard, features)
    SYN-->>ANA: list[SynergyRow]
    ANA->>INT: generate_interpretation(...)
    INT-->>ANA: interpretation text
    ANA->>REP: generate_markdown_report(...)
    REP-->>ANA: markdown report path
    ANA-->>APP: stores analysis in st.session_state
    APP-->>User: Updates live/analysis panels
```

## 1.5 Frontend Data Flow Diagram

```mermaid
flowchart LR
    User((User))
    UI["ui/app.py<br/>Streamlit controls/forms"]
    Session["st.session_state"]
    Agents["FeatureSubsetAgent configs"]
    Results["Tournament results<br/>list[GameResult]"]
    Analysis["Leaderboard + marginals + synergies + interpretation"]
    Reports["Markdown report"]
    Files[(outputs/data + outputs/reports)]
    BoardUI["Board SVG/HTML viewer"]

    User -->|select features/variant/settings| UI
    UI -->|store UI state| Session
    UI -->|generate selected agents| Agents
    Agents -->|passed to tournament| Results
    Results -->|saved/loaded| Files
    Results --> Analysis
    Analysis --> Reports
    Reports --> Files
    Session --> UI
    UI --> BoardUI
    BoardUI --> User
    Analysis --> UI
    UI --> User
```

## 1.6 Frontend Package Diagram

```mermaid
flowchart TB
    subgraph ui["ui package"]
        app["app.py"]
        board["board.py"]
        chess_viewer["chess_viewer.py"]
        play_engine["play_engine.py"]
        constants["constants.py"]
        init["__init__.py"]
    end

    app --> constants
    app --> board
    app --> chess_viewer
    app --> play_engine

    app --> agents["agents package"]
    app --> tournament["tournament package"]
    app --> analysis["analysis package"]
    app --> reports["reports package"]
    app --> features["features package"]

    play_engine --> core["core package"]
    play_engine --> search["search package"]
    play_engine --> agents

    board --> chesslib["chess / chess.svg external libs"]
    chess_viewer --> streamlit_components["streamlit.components.v1"]
```

## 1.7 Frontend Class/Module Diagram

The UI package has no user-defined classes. This diagram maps actual UI modules and functions.

```mermaid
classDiagram
    class ui_app {
        <<module>>
        +main()
        +_init_session_state()
        +_start_tournament()
        +_run_tournament_thread(config)
        +_analyze_results(results, features, variant, config)
        +_engine_reply(fen)
        +_render_board_area()
        +_render_build_panel()
        +_render_live_panel()
        +_render_analysis_panel()
        +_render_play_panel()
    }

    class ui_board {
        <<module>>
        +render_board(fen, last_move_uci, orientation, exploded_squares)
        +starting_fen()
        -_parse_uci_move(last_move_uci)
        -_build_explosion_fill(exploded_squares)
    }

    class ui_chess_viewer {
        <<module>>
        +chess_game_viewer(moves, white_name, black_name, result, height)
        +chess_play_interactive(fen, engine_name, engine_features_html, height)
        +chess_play_board(fen, height)
    }

    class ui_play_engine {
        <<module>>
        +engine_reply(fen, features, depth, variant, seed)
        +apply_san_move(fen, san)
        +game_status(fen)
    }

    class ui_constants {
        <<module>>
        +ALL_FEATURES
        +FEATURE_DISPLAY_NAMES
        +SESSION_DEFAULTS
        +VARIANT_DESCRIPTIONS
    }

    ui_app --> ui_board
    ui_app --> ui_chess_viewer
    ui_app --> ui_play_engine
    ui_app --> ui_constants
```

## 1.8 Frontend Activity Diagram — User Play Panel

```mermaid
flowchart TD
    Start([Open Play Panel])
    Init["Initialize board FEN/session values"]
    Render["Render board via chess_play_interactive()/render_board()"]
    UserMove{"User submits move?"}
    Validate["python-chess validates move/SAN/UCI in UI path"]
    EngineCall["ui/app.py _engine_reply(fen) or ui/play_engine.engine_reply()"]
    BuildAgent["Create FeatureSubsetAgent from selected features"]
    BuildEngine["Create AlphaBetaEngine(agent, depth, variant)"]
    Choose["engine.choose_move(Board.from_fen(fen))"]
    Push["Apply returned UCI move to chess.Board"]
    Status["game_status(fen)"]
    EndCheck{"Game over?"}
    Done([Show result])
    Loop["Update session FEN and re-render"]

    Start --> Init --> Render --> UserMove
    UserMove -- No --> Render
    UserMove -- Yes --> Validate --> EngineCall --> BuildAgent --> BuildEngine --> Choose --> Push --> Status --> EndCheck
    EndCheck -- Yes --> Done
    EndCheck -- No --> Loop --> Render
```

---

# 2. Backend Architecture — Engine, Simulation, Analysis, Reporting

## 2.1 Backend C4 Model

```mermaid
C4Context
    title Backend C4 Context - Python Engine and Analysis Modules

    Person(caller, "Caller", "Streamlit UI, Typer CLI, tests, or export script")

    System_Boundary(backend, "Backend Python Code") {
        Container(core, "core package", "Python", "Board, Move, coordinates, move application/generation")
        Container(variants, "variants package", "Python", "standard, atomic, antichess dispatch and rules")
        Container(features, "features package", "Python", "Material, mobility, king safety, pawn structure, etc.")
        Container(agents, "agents package", "Python", "FeatureSubsetAgent, agent generation, evaluation")
        Container(search, "search/alpha_beta.py", "Python", "AlphaBetaEngine negamax search")
        Container(simulation, "simulation package", "Python", "play_game(), GameResult, RandomAgent support")
        Container(tournament, "tournament package", "Python", "round-robin execution, leaderboard, result IO")
        Container(analysis, "analysis package", "Python", "Feature marginals, pairwise synergy, interpretation")
        Container(reports, "reports package", "Python", "Markdown report generation")
    }

    System_Ext(files, "Local Filesystem", "JSON/CSV/Markdown outputs")

    Rel(caller, simulation, "Runs games")
    Rel(caller, tournament, "Runs tournaments")
    Rel(caller, analysis, "Analyzes completed results")
    Rel(simulation, search, "Builds/uses AlphaBetaEngine")
    Rel(search, agents, "Evaluates board using agent")
    Rel(agents, features, "Calls feature functions from registry")
    Rel(search, variants, "Gets variant move/apply functions")
    Rel(variants, core, "Uses Board, Move, apply/generate")
    Rel(tournament, simulation, "Calls play_game()")
    Rel(tournament, files, "Saves/loads JSON/CSV")
    Rel(reports, files, "Writes Markdown report")
```

## 2.2 Backend Component Diagram

```mermaid
flowchart TB
    subgraph Core["core"]
        Board["Board<br/>starting_position(), copy(), get_piece(), set_piece(), find_king(), is_terminal(), to_fen(), from_fen()"]
        Move["Move<br/>to_uci(), __str__()"]
        Types["types.py<br/>piece_color(), piece_type(), opponent_color()"]
        Coords["coordinates.py<br/>square_to_algebraic(), algebraic_to_square()"]
        Apply["apply_move.py<br/>apply_move()"]
        MoveGen["move_generation.py<br/>generate_legal_moves(), generate_moves(), is_in_check(), is_square_attacked()"]
    end

    subgraph Variants["variants"]
        Dispatch["base.py<br/>get_apply_move()<br/>get_generate_legal_moves()"]
        Standard["standard.py"]
        Atomic["atomic.py"]
        Antichess["antichess.py"]
    end

    subgraph AgentsSearch["agents + search"]
        Agent["FeatureSubsetAgent dataclass"]
        GenAgents["generate_feature_subset_agents()"]
        Eval["evaluation.evaluate()<br/>contributions()"]
        AB["AlphaBetaEngine<br/>choose_move(), _negamax(), _order_moves()"]
    end

    subgraph FeatureLayer["features"]
        Registry["registry.FEATURES"]
        Material["material()"]
        Mobility["mobility()"]
        Center["center_control()"]
        KingSafety["king_safety()"]
        KingDanger["enemy_king_danger()"]
        Pawn["pawn_structure()"]
        Bishop["bishop_pair()"]
        Rook["rook_activity()"]
        Capture["capture_threats()"]
        Position["piece_position()"]
    end

    subgraph SimulationTournament["simulation + tournament"]
        PlayGame["simulation.game.play_game()"]
        GameResult["GameResult dataclass"]
        RandomAgent["RandomAgent"]
        RoundRobin["run_round_robin()"]
        Leaderboard["compute_leaderboard()"]
        ResultsIO["save_results_json/load_results_json/save_results_csv"]
    end

    subgraph AnalysisReports["analysis + reports"]
        Marginals["compute_feature_marginals()"]
        Synergy["compute_pairwise_synergies()"]
        Interpretation["generate_interpretation()"]
        Markdown["generate_markdown_report()"]
        Export["export_data.export_all()"]
    end

    Board --> Coords
    Apply --> Board
    Apply --> Move
    Apply --> Types
    MoveGen --> Board
    MoveGen --> Move
    MoveGen --> Types
    MoveGen --> Apply

    Dispatch --> Standard
    Dispatch --> Atomic
    Dispatch --> Antichess
    Standard --> Apply
    Standard --> MoveGen
    Atomic --> Apply
    Atomic --> MoveGen
    Antichess --> Apply
    Antichess --> MoveGen

    AB --> Dispatch
    AB --> Eval
    AB --> Agent
    AB --> Board
    Eval --> Registry
    Registry --> Material
    Registry --> Mobility
    Registry --> Center
    Registry --> KingSafety
    Registry --> KingDanger
    Registry --> Pawn
    Registry --> Bishop
    Registry --> Rook
    Registry --> Capture
    Registry --> Position

    PlayGame --> Board
    PlayGame --> Dispatch
    PlayGame --> AB
    PlayGame --> RandomAgent
    PlayGame --> GameResult
    RoundRobin --> PlayGame
    Leaderboard --> GameResult
    ResultsIO --> GameResult

    Marginals --> Leaderboard
    Synergy --> Leaderboard
    Interpretation --> Marginals
    Interpretation --> Synergy
    Markdown --> Leaderboard
    Markdown --> Marginals
    Markdown --> Synergy
    Export --> ResultsIO
    Export --> Leaderboard
    Export --> Marginals
    Export --> Synergy
    Export --> Interpretation
```

## 2.3 Backend Deployment Diagram

```mermaid
flowchart LR
    subgraph Runtime["Python Runtime"]
        CLI["main.py Typer CLI"]
        StreamlitCaller["ui/app.py caller"]
        ExportScript["export_data.py"]
        BackendModules["Backend modules<br/>core, variants, agents, search, simulation, tournament, analysis, reports"]
    end

    subgraph FS["Local Filesystem"]
        JSON["outputs/data/tournament_results_*.json"]
        CSV["outputs/data/*.csv"]
        MD["outputs/reports/*_strategy_report.md"]
    end

    CLI --> BackendModules
    StreamlitCaller --> BackendModules
    ExportScript --> BackendModules
    BackendModules --> JSON
    BackendModules --> CSV
    BackendModules --> MD
    JSON --> BackendModules
```

## 2.4 Backend Sequence Diagram — `play_game()`

```mermaid
sequenceDiagram
    participant Caller
    participant Game as simulation.game.play_game()
    participant Board as Board.starting_position()
    participant Var as variants.base
    participant Engine as AlphaBetaEngine
    participant Gen as generate legal moves fn
    participant Search as AlphaBetaEngine.choose_move()
    participant Eval as evaluation.evaluate()
    participant Features as features.registry.FEATURES
    participant Apply as apply move fn
    participant Result as GameResult

    Caller->>Game: play_game(white_agent, black_agent, variant, ...)
    Game->>Board: starting_position()
    Board-->>Game: Board
    Game->>Var: get_apply_move(variant)
    Var-->>Game: apply_fn
    Game->>Var: get_generate_legal_moves(variant)
    Var-->>Game: gen_legal_fn

    loop until terminal/max moves/no legal moves
        Game->>Engine: _make_engine(agent, depth, variant)
        Engine-->>Game: AlphaBetaEngine
        Game->>Search: choose_move(board)
        Search->>Gen: legal moves via variant dispatch
        Gen-->>Search: list[Move]
        Search->>Search: _negamax(board, depth, alpha, beta, color)
        Search->>Eval: evaluate(board, color, agent)
        Eval->>Features: call selected feature functions
        Features-->>Eval: feature scores
        Eval-->>Search: numeric score
        Search-->>Game: Move
        Game->>Apply: apply_fn(board, move)
        Apply-->>Game: new Board
    end

    Game->>Result: GameResult(...)
    Result-->>Caller: result
```

## 2.5 Backend Data Flow Diagram

```mermaid
flowchart LR
    AgentConfig["FeatureSubsetAgent<br/>name/features/weights/depth"]
    BoardState["Board<br/>grid, side_to_move, castling, en_passant, clocks"]
    VariantName["variant string<br/>standard/atomic/antichess"]
    Dispatch["variants.base dispatch"]
    LegalMoves["list[Move]"]
    Evaluation["evaluation score"]
    FeatureFns["selected feature functions"]
    Search["AlphaBetaEngine"]
    MoveChosen["chosen Move"]
    GameResult["GameResult"]
    ResultsFile[(JSON/CSV files)]
    Leaderboard["LeaderboardRow list"]
    AnalysisRows["FeatureContributionRow + SynergyRow"]
    Report[(Markdown report)]

    AgentConfig --> Search
    BoardState --> Search
    VariantName --> Dispatch
    Dispatch --> LegalMoves
    LegalMoves --> Search
    BoardState --> FeatureFns
    AgentConfig --> FeatureFns
    FeatureFns --> Evaluation
    Evaluation --> Search
    Search --> MoveChosen
    MoveChosen --> BoardState
    BoardState --> GameResult
    AgentConfig --> GameResult
    GameResult --> ResultsFile
    GameResult --> Leaderboard
    Leaderboard --> AnalysisRows
    Leaderboard --> Report
    AnalysisRows --> Report
```

## 2.6 Backend Package Diagram

```mermaid
flowchart TB
    main["main.py"]
    export["export_data.py"]

    core["core"]
    variants["variants"]
    features["features"]
    agents["agents"]
    search["search"]
    simulation["simulation"]
    tournament["tournament"]
    analysis["analysis"]
    reports["reports"]

    main --> agents
    main --> simulation
    main --> tournament
    main --> analysis
    main --> reports
    main --> core
    main --> variants
    main --> search

    export --> tournament
    export --> analysis
    export --> agents

    variants --> core
    features --> core
    features --> core_movegen["core.move_generation"]
    agents --> features
    agents --> core
    search --> agents
    search --> variants
    search --> core
    simulation --> search
    simulation --> variants
    simulation --> agents
    simulation --> core
    tournament --> simulation
    tournament --> agents
    analysis --> tournament
    reports --> tournament
    reports --> analysis
```

## 2.7 Backend Class Diagram

```mermaid
classDiagram
    class Board {
        +grid
        +side_to_move
        +castling_rights
        +en_passant_target
        +halfmove_clock
        +fullmove_number
        +starting_position() Board
        +copy() Board
        +get_piece(square) str
        +set_piece(square, piece)
        +find_king(color)
        +is_terminal() bool
        +to_fen() str
        +from_fen(fen) Board
        +print_board()
    }

    class Move {
        +from_square
        +to_square
        +promotion
        +is_en_passant
        +is_castling
        +to_uci() str
        +__str__() str
    }

    class FeatureSubsetAgent {
        +name
        +features
        +weights
        +depth
    }

    class AlphaBetaEngine {
        -agent
        -max_depth
        -variant
        -_nodes
        -_last_search_time
        -_apply_fn
        -_gen_legal_fn
        +nodes_searched() int
        +search_time_seconds() float
        +choose_move(board) Move
        -_negamax(board, depth, alpha, beta, color) float
        -_order_moves(board, moves) list
    }

    class RandomAgent {
        -variant
        -_rng
        +choose_move(board) Move
    }

    class GameResult {
        +white_agent
        +black_agent
        +winner
        +draw
        +moves
        +plies
        +termination
        +variant
        +white_nodes
        +black_nodes
        +white_avg_search_time
        +black_avg_search_time
    }

    class LeaderboardRow {
        +agent_name
        +features
        +games
        +wins
        +losses
        +draws
        +score
        +score_rate
        +avg_nodes
        +avg_search_time
    }

    class FeatureContributionRow {
        +feature
        +with_count
        +without_count
        +with_score_rate
        +without_score_rate
        +delta
    }

    class SynergyRow {
        +feature_a
        +feature_b
        +together_count
        +together_score_rate
        +expected_additive
        +synergy
    }

    Board --> Move : apply/generate uses
    AlphaBetaEngine --> FeatureSubsetAgent
    AlphaBetaEngine --> Board
    AlphaBetaEngine --> Move
    RandomAgent --> Move
    GameResult --> FeatureSubsetAgent : stores agent names/features indirectly
    LeaderboardRow --> GameResult : computed from
    FeatureContributionRow --> LeaderboardRow : computed from
    SynergyRow --> LeaderboardRow : computed from
```

## 2.8 Backend Activity Diagram — Tournament + Analysis

```mermaid
flowchart TD
    Start([Start backend tournament])
    Agents["Receive/generated list[FeatureSubsetAgent]"]
    RoundRobin["run_round_robin()"]
    PairLoop{"More agent pairs/games?"}
    Play["play_game()"]
    BoardInit["Board.starting_position()"]
    VariantFns["get_apply_move() + get_generate_legal_moves()"]
    SearchMove["AlphaBetaEngine.choose_move() or RandomAgent.choose_move()"]
    Apply["apply variant move"]
    EndGame{"Terminal/max moves/no moves?"}
    Result["Create GameResult"]
    Save["save_results_json()/save_results_csv()"]
    Leaderboard["compute_leaderboard()"]
    Marginals["compute_feature_marginals()"]
    Synergies["compute_pairwise_synergies()"]
    Interpretation["generate_interpretation()"]
    Report["generate_markdown_report()"]
    Done([Done])

    Start --> Agents --> RoundRobin --> PairLoop
    PairLoop -- Yes --> Play --> BoardInit --> VariantFns --> SearchMove --> Apply --> EndGame
    EndGame -- No --> SearchMove
    EndGame -- Yes --> Result --> PairLoop
    PairLoop -- No --> Save --> Leaderboard --> Marginals --> Synergies --> Interpretation --> Report --> Done
```

---

# 3. Whole Project Architecture — UI + CLI + Shared Backend + Files

## 3.1 Whole Project C4 Model

```mermaid
C4Context
    title Whole Project C4 Context

    Person(user, "User", "Runs Streamlit UI or CLI")
    System_Boundary(project, "p72cubist-main-2") {
        Container(streamlit, "ui/app.py", "Streamlit", "Interactive browser UI")
        Container(cli, "main.py", "Typer CLI", "Command line entrypoint: random-game, match, tournament, analyze, full-pipeline, play")
        Container(exporter, "export_data.py", "Python script", "Exports richer CSV/JSON analysis datasets")
        Container(shared_backend, "Shared backend packages", "Python", "core, variants, agents, search, simulation, tournament, analysis, reports")
        Container(outputs, "outputs/", "Filesystem", "Tournament JSON, CSV datasets, Markdown reports")
    }

    Rel(user, streamlit, "Runs/uses UI")
    Rel(user, cli, "Runs commands")
    Rel(user, exporter, "Runs export script")
    Rel(streamlit, shared_backend, "Direct imports and function calls")
    Rel(cli, shared_backend, "Direct imports and function calls")
    Rel(exporter, shared_backend, "Direct imports and function calls")
    Rel(shared_backend, outputs, "Read/write results and reports")
    Rel(streamlit, outputs, "Load existing JSON and show reports")
```

## 3.2 Whole Project Component Diagram

```mermaid
flowchart TB
    User((User))

    subgraph EntryPoints["Entry points"]
        UI["ui/app.py<br/>Streamlit app"]
        CLI["main.py<br/>Typer commands"]
        EXPORT["export_data.py<br/>data export pipeline"]
    end

    subgraph SharedBackend["Shared backend"]
        Agents["agents<br/>FeatureSubsetAgent<br/>generate agents<br/>evaluate"]
        Search["search<br/>AlphaBetaEngine"]
        Simulation["simulation<br/>play_game()<br/>GameResult<br/>RandomAgent"]
        Tournament["tournament<br/>run_round_robin<br/>leaderboard<br/>results_io"]
        Analysis["analysis<br/>marginals<br/>synergy<br/>interpretation"]
        Reports["reports<br/>markdown_report"]
        Features["features<br/>registry + feature functions"]
        Variants["variants<br/>standard/atomic/antichess dispatch"]
        Core["core<br/>Board, Move, move generation/application"]
    end

    subgraph Files["Local outputs"]
        JSON["outputs/data/*.json"]
        CSV["outputs/data/*.csv"]
        MD["outputs/reports/*.md"]
    end

    User --> UI
    User --> CLI
    User --> EXPORT

    UI --> Agents
    UI --> Tournament
    UI --> Analysis
    UI --> Reports
    UI --> JSON
    UI --> MD

    CLI --> Simulation
    CLI --> Tournament
    CLI --> Analysis
    CLI --> Reports
    CLI --> Core
    CLI --> Search

    EXPORT --> JSON
    EXPORT --> CSV
    EXPORT --> Analysis
    EXPORT --> Tournament

    Tournament --> Simulation
    Simulation --> Search
    Search --> Agents
    Agents --> Features
    Search --> Variants
    Simulation --> Variants
    Variants --> Core
    Features --> Core
    Tournament --> JSON
    Tournament --> CSV
    Reports --> MD
```

## 3.3 Whole Project Deployment Diagram

```mermaid
flowchart TB
    subgraph DeveloperMachine["Developer/User Machine"]
        Browser["Browser"]
        Shell["Terminal/Shell"]

        subgraph PythonEnv["Python environment"]
            StreamlitServer["Streamlit server<br/>streamlit run ui/app.py"]
            TyperCLI["Typer CLI<br/>python main.py ..."]
            ExportProcess["Export script<br/>python export_data.py"]
            Packages["Project Python packages"]
        end

        subgraph LocalDisk["Local disk"]
            Source["Source code files"]
            Outputs["outputs/data + outputs/reports"]
            Config[".streamlit/config.toml"]
        end
    end

    Browser <-->|localhost Streamlit HTTP| StreamlitServer
    Shell --> TyperCLI
    Shell --> ExportProcess
    StreamlitServer --> Packages
    TyperCLI --> Packages
    ExportProcess --> Packages
    Packages --> Outputs
    Outputs --> Packages
    PythonEnv --> Source
    StreamlitServer --> Config
```

## 3.4 Whole Project Sequence Diagram — Full Pipeline via CLI

```mermaid
sequenceDiagram
    actor User
    participant CLI as main.py full_pipeline()
    participant AG as _get_agents()/generate_feature_subset_agents()
    participant RR as run_round_robin()
    participant GAME as play_game()
    participant SEARCH as AlphaBetaEngine
    participant IO as results_io
    participant LB as compute_leaderboard()
    participant FM as compute_feature_marginals()
    participant SYN as compute_pairwise_synergies()
    participant INT as generate_interpretation()
    participant REP as generate_markdown_report()

    User->>CLI: python main.py full-pipeline ...
    CLI->>AG: create selected FeatureSubsetAgent list
    AG-->>CLI: agents
    CLI->>RR: run_round_robin(agents, ...)
    loop each scheduled game
        RR->>GAME: play_game(white, black, ...)
        GAME->>SEARCH: choose_move(board)
        SEARCH-->>GAME: move
        GAME-->>RR: GameResult
    end
    RR-->>CLI: list[GameResult]
    CLI->>IO: save_results_json(results, path)
    CLI->>IO: save_results_csv(results, path)
    CLI->>LB: compute_leaderboard(results, agents)
    LB-->>CLI: leaderboard rows
    CLI->>FM: compute_feature_marginals(leaderboard, features)
    CLI->>SYN: compute_pairwise_synergies(leaderboard, features)
    CLI->>INT: generate_interpretation(...)
    CLI->>REP: generate_markdown_report(...)
    REP-->>CLI: report path
    CLI-->>User: Console tables + output paths
```

## 3.5 Whole Project Data Flow Diagram

```mermaid
flowchart LR
    UserInput["User input<br/>UI controls or CLI args"]
    AgentSelection["Feature list, agent count, depth, seed"]
    AgentObjects["FeatureSubsetAgent objects"]
    GameEngine["Simulation + AlphaBetaEngine"]
    RuleSystem["Variant dispatch + core chess rules"]
    FeatureEval["Feature evaluation registry"]
    Results["GameResult list"]
    JSON[(Tournament JSON)]
    CSV[(CSV exports)]
    Leaderboard["Leaderboard rows"]
    Analysis["Marginals + Synergies + Interpretation"]
    Markdown[(Markdown report)]
    UIOutput["Streamlit charts/tables/board"]
    CLIOutput["Rich console tables"]

    UserInput --> AgentSelection
    AgentSelection --> AgentObjects
    AgentObjects --> GameEngine
    RuleSystem --> GameEngine
    FeatureEval --> GameEngine
    GameEngine --> Results
    Results --> JSON
    Results --> CSV
    Results --> Leaderboard
    Leaderboard --> Analysis
    Analysis --> Markdown
    JSON --> UIOutput
    Leaderboard --> UIOutput
    Analysis --> UIOutput
    Leaderboard --> CLIOutput
    Analysis --> CLIOutput
```

## 3.6 Whole Project Package Diagram

```mermaid
flowchart TB
    root["project root"]

    root --> main_py["main.py"]
    root --> export_py["export_data.py"]
    root --> ui_pkg["ui"]
    root --> core_pkg["core"]
    root --> variants_pkg["variants"]
    root --> agents_pkg["agents"]
    root --> features_pkg["features"]
    root --> search_pkg["search"]
    root --> simulation_pkg["simulation"]
    root --> tournament_pkg["tournament"]
    root --> analysis_pkg["analysis"]
    root --> reports_pkg["reports"]
    root --> tests_pkg["tests"]
    root --> outputs_dir["outputs"]

    ui_pkg --> agents_pkg
    ui_pkg --> tournament_pkg
    ui_pkg --> analysis_pkg
    ui_pkg --> reports_pkg
    ui_pkg --> features_pkg
    ui_pkg --> search_pkg
    ui_pkg --> core_pkg

    main_py --> agents_pkg
    main_py --> simulation_pkg
    main_py --> tournament_pkg
    main_py --> analysis_pkg
    main_py --> reports_pkg
    main_py --> core_pkg
    main_py --> variants_pkg
    main_py --> search_pkg

    export_py --> tournament_pkg
    export_py --> analysis_pkg
    export_py --> agents_pkg

    simulation_pkg --> search_pkg
    simulation_pkg --> variants_pkg
    simulation_pkg --> core_pkg
    simulation_pkg --> agents_pkg

    search_pkg --> agents_pkg
    search_pkg --> variants_pkg
    search_pkg --> core_pkg

    agents_pkg --> features_pkg
    features_pkg --> core_pkg
    variants_pkg --> core_pkg
    tournament_pkg --> simulation_pkg
    analysis_pkg --> tournament_pkg
    reports_pkg --> tournament_pkg
    reports_pkg --> analysis_pkg

    tests_pkg --> core_pkg
    tests_pkg --> variants_pkg
    tests_pkg --> features_pkg
    tests_pkg --> agents_pkg
    tests_pkg --> search_pkg
    tests_pkg --> simulation_pkg
    tests_pkg --> tournament_pkg
    tests_pkg --> analysis_pkg
```

## 3.7 Whole Project Class Diagram

```mermaid
classDiagram
    class StreamlitUI {
        <<module ui/app.py>>
        +main()
        +_start_tournament()
        +_run_tournament_thread(config)
        +_analyze_results(results, features, variant, config)
    }

    class CLI {
        <<module main.py>>
        +random_game()
        +match()
        +tournament()
        +analyze()
        +full_pipeline()
        +play()
    }

    class Board {
        +starting_position() Board
        +copy() Board
        +get_piece(square)
        +set_piece(square,piece)
        +find_king(color)
        +is_terminal()
        +to_fen()
        +from_fen(fen)
    }

    class Move {
        +from_square
        +to_square
        +promotion
        +is_en_passant
        +is_castling
        +to_uci()
    }

    class FeatureSubsetAgent {
        +name
        +features
        +weights
        +depth
    }

    class AlphaBetaEngine {
        +choose_move(board)
        -_negamax(board, depth, alpha, beta, color)
        -_order_moves(board, moves)
    }

    class RandomAgent {
        +choose_move(board)
    }

    class GameResult {
        +white_agent
        +black_agent
        +winner
        +draw
        +moves
        +plies
        +termination
        +variant
    }

    class LeaderboardRow {
        +agent_name
        +features
        +games
        +wins
        +losses
        +draws
        +score
        +score_rate
    }

    class FeatureContributionRow {
        +feature
        +delta
    }

    class SynergyRow {
        +feature_a
        +feature_b
        +synergy
    }

    StreamlitUI --> FeatureSubsetAgent
    StreamlitUI --> GameResult
    StreamlitUI --> LeaderboardRow
    CLI --> FeatureSubsetAgent
    CLI --> GameResult
    CLI --> LeaderboardRow
    AlphaBetaEngine --> FeatureSubsetAgent
    AlphaBetaEngine --> Board
    AlphaBetaEngine --> Move
    RandomAgent --> Board
    RandomAgent --> Move
    GameResult --> Move : stores UCI move strings
    LeaderboardRow --> GameResult : computed from
    FeatureContributionRow --> LeaderboardRow : computed from
    SynergyRow --> LeaderboardRow : computed from
```

## 3.8 Whole Project Activity Diagram

```mermaid
flowchart TD
    Start([User starts project])
    Entry{"Entry point?"}

    UIStart["Streamlit UI: ui/app.py main()"]
    CLIStart["CLI: main.py command"]
    ExportStart["Export: export_data.py export_all()"]

    Configure["Choose variant/features/agents/depth/games/seed"]
    GenerateAgents["generate_feature_subset_agents() or _get_agents()"]
    RunTournament{"Tournament/match/play?"}
    SingleGame["simulation.game.play_game()"]
    RoundRobin["tournament.round_robin.run_round_robin()"]
    Interactive["main.py play() or UI play panel"]

    Analyze{"Analyze results?"}
    SaveResults["results_io save/load JSON/CSV"]
    Leaderboard["compute_leaderboard()"]
    Marginals["compute_feature_marginals()"]
    Synergy["compute_pairwise_synergies()"]
    Interpret["generate_interpretation()"]
    Report["generate_markdown_report()"]
    Render["Render UI tables/charts/board or CLI Rich tables"]
    Done([Done])

    Start --> Entry
    Entry -- UI --> UIStart --> Configure
    Entry -- CLI --> CLIStart --> Configure
    Entry -- Export existing results --> ExportStart --> SaveResults

    Configure --> GenerateAgents --> RunTournament
    RunTournament -- single/match/play_game --> SingleGame
    RunTournament -- round robin --> RoundRobin
    RunTournament -- interactive play --> Interactive

    SingleGame --> SaveResults
    RoundRobin --> SaveResults
    Interactive --> Render

    SaveResults --> Analyze
    Analyze -- yes --> Leaderboard --> Marginals --> Synergy --> Interpret --> Report --> Render --> Done
    Analyze -- no --> Render --> Done
```

---

# Code-Trace Notes Used for the Diagrams

## Real entry points

```mermaid
flowchart LR
    UI["ui/app.py main()"]
    CLI["main.py Typer app commands"]
    Export["export_data.py export_all()"]

    UI --> Backend["Shared Python backend modules"]
    CLI --> Backend
    Export --> Backend
```

## Real backend move-search path

```mermaid
flowchart TD
    A["AlphaBetaEngine.choose_move(board)"]
    B["variant generate legal moves fn<br/>from get_generate_legal_moves(variant)"]
    C["_order_moves(board, legal_moves)"]
    D["_negamax(board, depth, alpha, beta, color)"]
    E["variant apply move fn<br/>from get_apply_move(variant)"]
    F["evaluation.evaluate(board, color, agent)"]
    G["features.registry.FEATURES"]
    H["selected feature functions"]

    A --> B --> C --> D
    D --> E
    D --> F --> G --> H
```

## Real tournament-analysis-report path

```mermaid
flowchart TD
    A["run_round_robin(agents, ...)"]
    B["play_game(...)"]
    C["list[GameResult]"]
    D["save_results_json()/save_results_csv()"]
    E["compute_leaderboard()"]
    F["compute_feature_marginals()"]
    G["compute_pairwise_synergies()"]
    H["generate_interpretation()"]
    I["generate_markdown_report()"]

    A --> B --> C --> D --> E --> F --> G --> H --> I
```
