# Auction and routing

## Bid lifecycle

1. The order desk sends `TASK_REQUEST` with task details and an epoch.
2. Each receiving agent evaluates the task independently.
3. An eligible agent broadcasts `TASK_BID` with its cost.
4. Agents collect bids for the configured window and resolve by lowest cost, then lowest agent ID.
5. The selected agent sends `TASK_ACCEPT`; the UI audit panel records bids and acceptance claims from actual bus sends.

Use **A** to open the auction panel and **Left/Right** to browse recorded auctions. “No bid recorded” means no bid transmission was observed; under message loss, it does not prove the agent was ineligible.

## Current bid formula

Lower cost wins:

```text
cost = W_TIME × (PRIORITY_FACTOR[priority] × time_until_pickup + delivery_time)
       + W_LOAD × tasks_already_held
```

The current defaults are `W_TIME = 1.0`, `W_LOAD = 5.0`, and priority factors `0.5`, `1.0`, and `2.0` for low, medium, and high priority. Higher priority makes time until pickup count more in the agent's cost. The formula is an explainable heuristic, not an optimized or learned policy.

Battery is a **feasibility check**, not a term added to the bid cost. An agent does not bid if it cannot cover its active/queued work, the candidate task, and a trip from the end of its planned route to a charger, with a 20% safety margin. It also cannot bid while failed, charging, heading to charge, or at the queue limit.

The route estimate follows the same ordering as execution: active task first, then queued work sorted by priority, creation time, and task ID. This keeps its ETA and battery check aligned with its planned task order.

## Routing

The world is a four-direction grid. A* uses Manhattan distance as its heuristic and returns a shortest route around known blocked cells. When a road change affects an agent's route, the agent clears/replans its path. The map generator and interactive road-blocking action preserve connectivity, so the demo avoids intentionally disconnected maps.

## What the auction panel can and cannot say

It can show task ID, priority, epoch, each transmitted bid, observed accept claims, and whether the accepted cost matches the lowest recorded bid. It can expose conflicting claims. It cannot prove which bids every agent received, because the bus can drop messages and the panel is a simulation-wide observer of sends.
