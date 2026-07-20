---
id: ADR-001
status: accepted
---

# Publish order events

## Context

Checkout and fulfillment must evolve independently.

## Decision

Checkout must publish OrderPlaced events in production.

```mermaid
graph LR
Checkout --> Orders : publishes OrderPlaced
```

## Consequences

Consumers may process an event more than once.
