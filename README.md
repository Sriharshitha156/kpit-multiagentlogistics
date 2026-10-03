# Smart Multi-Agent Delivery Simulator

KPIT K-IMPACT 2.0 project: decentralized multi-agent coordination for an autonomous EV delivery fleet.
Vehicles allocate tasks through auctions, bid only for jobs their battery can finish, detect dead peers from
missing heartbeats, and reclaim orphaned deliveries from their own ledgers. There is no central controller.

## Run it
    pip install -r requirements.txt
    python main.py            # interactive window
    python main.py --split    # start in split-screen (B2 central vs auction)
    python -m unittest discover -s tests

## Keys
SPACE pause | UP/DOWN speed | R new map | TAB switch strategy | S split screen
1 rush hour | 2 failure storm | 3 blocked road | D dispatcher on/off | H heartbeats in feed
Click a vehicle to fail it | right-click a cell to block it | ESC quit

## Experiments (headless, real simulation runs)
    python experiments/run_experiments.py --suite sweep   # failure-timeout vs message-loss sweep (tuning seeds)
    python experiments/run_experiments.py --suite main    # main experiments on fresh test seeds (about 10 minutes)
    python experiments/make_charts.py --suite main
Results are written to results/<suite>/ (raw_runs.csv, summary.csv, settings.json, charts/).

## Files
config.py (all tunable numbers) | task.py | environment.py | pathfinding.py (A*) | communication.py (message bus)
agent.py (auction, ledger, heartbeats, reclaim) | baseline_dispatcher.py (B1 naive, B2 smart central)
simulation.py (tick loop) | metrics.py | scenarios.py (demo presets) | main.py (Pygame) | experiments/ | tests/

## Honest limitations
The network is simulated inside one program. Agents may share a cell (no collision avoidance). Failures are
permanent. Chargers have unlimited capacity. After a crash the parcel position is simplified to the last
heartbeat position. The baselines have no message cost modelled. See the report for the full list.
