# Failure and recovery

## What happens after a vehicle fails?

1. A vehicle stops updating and sending heartbeats.
2. Each surviving agent independently checks how long it has been since it heard from peers.
3. After the configured timeout, an agent can mark the silent peer as suspected failed.
4. Agents inspect their own task ledgers for unfinished tasks owned by that peer.
5. They create a new auction epoch and bid if they can feasibly take the work.
6. The selected replacement announces acceptance; surviving agents update their task ledgers.

The timeout is currently 15 silent ticks. Heartbeats are staggered at a 3-tick interval and messages have a 1-tick delay by default. Exact recovery timing depends on when the failure occurs relative to the last heartbeat and auction/message timing.

## If the failed vehicle was carrying a parcel

The simulation uses the failed carrier's last heartbeat position as the approximate parcel pickup point. The parcel is not physically modelled, and that location can be stale by up to roughly a heartbeat interval (or longer with message loss).

## How to demonstrate

Close the welcome/help overlay if it is open, then press 4 for a deterministic setup: it resets to a clean simulation, creates a battery-feasible high-priority task at Agent 1's current cell, lets the strategy allocate it, advances until pickup, and fails the carrier. Then watch the message feed as peers detect the failure and re-auction the task. Recovery is not instantaneous; the current timeout is 15 silent ticks plus heartbeat/message timing.

For a less scripted run, create a rush-hour burst with 1, then click a vehicle with an active route. The owner fails immediately, and peers recover any unfinished work after their timeout.

In split-screen mode, B2 recovers with immediate central knowledge. That is intentionally faster and has an information advantage over the auction mode; it should not be described as an equal-information comparison.

## Recovery metrics

Each recovery event records the failed agent and failure tick, replacement agent, reassignment tick, recovery time, replacement route distance to the parcel, and whether the task eventually completed. The displayed recovery approach distance is not the distance increase over a counterfactual no-failure run.
