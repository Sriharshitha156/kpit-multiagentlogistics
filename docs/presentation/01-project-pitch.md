# Project pitch

## 30-second version

Imagine a neighbourhood delivery fleet with eight electric vans. Instead of a central dispatcher choosing a van for every order, each available van estimates the job using its own location, battery, and workload, then sends a bid. The agents choose the lowest bid using a shared rule. They also use charging stations and can re-auction work after a peer stops responding. This project simulates that coordination and compares it with central dispatch.

## Two-minute version

Our project explores decentralized task allocation for an electric delivery fleet. A request is announced to the fleet. Each agent independently checks whether it has room in its task queue and enough battery to complete its planned work and reach a charger. Eligible agents estimate their route and workload, then send a bid over a simulated message bus. Agents use the same lowest-cost rule, with agent ID as a tie-breaker, and the selected agent announces acceptance.

Vehicles route around obstacles using grid-based A*. Battery decreases with movement, and idle low-battery vehicles travel to a charging station. Agents send heartbeats. When a peer is silent long enough, surviving agents can mark it failed and re-auction its unfinished work. A split-screen view compares the auction fleet with central dispatch strategies.

The purpose is to study coordination, recovery, deadlines, and trade-offs under controlled simulation conditions. The default 90-minute delivery window uses an illustrative one-minute-per-tick clock; the model does not use real city maps or delivery data, and its numbers are simulation results under configurable assumptions.

## One-sentence problem statement

Can a fleet of autonomous EV agents allocate delivery work and recover from vehicle failures without a central task allocator?

## What is the contribution?

The demonstrable contribution is an understandable simulation of local bidding, peer failure detection, and task recovery, with central baselines and repeatable experiment scripts. Do not claim that auctions are always better; that conclusion must come from current, correctly paired experiment results.

For a repeatable live recovery sequence, press `4` to reset to a clean run, let the fleet auction a high-priority task, and fail its carrier after pickup. The demo then shows delayed peer detection, recovery bidding, reassignment, and delivery tracking.

## Everyday analogy

Think of delivery orders arriving in a neighbourhood. Each van checks, “Can I reach the pickup, deliver the parcel, and still get to a charger? How much work do I already have?” Vans that pass the feasibility checks bid. The lowest-cost bid wins. If that van later goes silent, the other vans can compete to take its task.
