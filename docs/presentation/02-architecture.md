# System architecture

## Decision and data flow

```mermaid
flowchart LR
  Desk[Order desk] -->|TASK_REQUEST| Bus[In-process message bus]
  Bus --> A1[Agent 1]
  Bus --> A2[Agent 2]
  Bus --> AN[Other agents]
  A1 -->|TASK_BID / TASK_ACCEPT / HEARTBEAT| Bus
  A2 -->|TASK_BID / TASK_ACCEPT / HEARTBEAT| Bus
  AN -->|TASK_BID / TASK_ACCEPT / HEARTBEAT| Bus
  Env[Environment: grid, tasks, chargers] --> Sim[Simulation tick loop]
  Sim -->|messages and tick| Bus
  Sim -->|update each agent| A1
  Sim -->|update each agent| A2
  Sim -->|update each agent| AN
  A1 -->|movement and task events| Env
  A2 -->|movement and task events| Env
  AN -->|movement and task events| Env
  Env --> Metrics[Metrics and rendering]
  B1B2[Central B1 / B2 baselines] -->|read agent state; assign centrally| Env
```

## Main components

- `simulation.py`: advances ticks, creates orders, delivers bus messages, and updates agents in shuffled order.
- `agent.py`: local state, bid calculation, auction ledger, task queue, heartbeats, failure detection, recovery, charging, and movement.
- `communication.py`: simulated delay/loss, message delivery, transmission counters, and the auction audit trail shown by the UI.
- `environment.py`: true grid, obstacles, chargers, task lifecycle, and ground-truth event recording.
- `pathfinding.py`: A* route search on the grid.
- `baseline_dispatcher.py`: intentionally centralized nearest-idle and battery-aware strategies.
- `metrics.py`: derives summary values from completed simulation events.
- `main.py`: Pygame rendering and user controls; it displays decisions and state but does not choose auction winners.

## Where are decisions made?

In auction mode, each agent calculates its own bid and independently resolves the bids it received. There is no central auction winner function. The deterministic rule is lowest cost, then lower agent ID. With message loss, agents can see different bid sets; the UI can show conflicting accept claims when this happens.

The order desk announces a new task, and the environment owns ground truth for the map and task status. Obstacle changes are delivered directly to each agent as simulation events. The simulated bus is an in-process component, not a real network.

The B1 and B2 strategies are central by design: the dispatcher reads agent state and assigns tasks. B2 also sees failures immediately. They are comparison baselines, not decentralized modes.

## Message purposes

| Message | Purpose |
|---|---|
| `TASK_REQUEST` | Order desk announces a task and auction epoch. |
| `TASK_BID` | Agent announces its cost for that task and epoch. |
| `TASK_ACCEPT` | Winning agent announces ownership. |
| `DELIVERY_COMPLETE` | Agent announces a completed delivery. |
| `HEARTBEAT` | Agent reports that it is alive and shares position/status. |
| `AGENT_FAILURE` | Peer announces that an agent is considered failed. |
| `TASK_REASSIGN` | Peer announces a new auction epoch for orphaned work. |

## How to explain decentralization honestly

Say: “Task allocation and failure suspicion are decided by individual agents from messages and local ledgers. The prototype still runs every agent and the message bus in one process, and the environment provides shared ground truth and simulated events.” Do not describe it as a distributed deployment or real vehicle-to-vehicle network.
