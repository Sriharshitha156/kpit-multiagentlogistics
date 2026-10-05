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

Create a rush-hour burst with `1`, then click a vehicle with an active route. Watch for the failure, heartbeat timeout, `AGENT_FAILURE` / `TASK_REASSIGN` messages, new bids, and acceptance. The replacement may not be the same agent on every run.

In split-screen mode, B2 recovers with immediate central knowledge. That is intentionally faster and has an information advantage over the auction mode; it should not be described as an equal-information comparison.

## Recovery metrics

The simulation records failure time, first detection time, reassignment time, task reassignment count, and eventual task completion through task status. It does not currently record extra recovery-only distance or a separate recovery-success rate. The “lost” display is a current failed-owner snapshot; a task can disappear from it after successful reassignment.
