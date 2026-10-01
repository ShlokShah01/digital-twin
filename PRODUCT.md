# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

A personal Digital Twin assistant that answers questions and weighs decisions using a learned writing profile, retrieved evidence, a knowledge graph, and Laya plus an optional remote LLM.

## Users

The user chose the Warm Ivory light mockup: an elegant cream chat workspace with bronze accents, a single compact sidebar, and profile/knowledge pages accessible from the bottom profile menu.

## Operating Context

A local Windows application at http://127.0.0.1:8000 with React/Vite served by FastAPI. Laya runs on the RTX 4050 through CUDA; the configured narrator uses NVIDIA's OpenAI-compatible endpoint.

## Capabilities and Constraints

Preserve all existing bot routes, choice scoring, evidence and metadata, profile and graph inspection, rebuilding, and persisted chat sessions (rename, archive, restore, delete). The user explicitly requires that the redesign not break the bot. Improve actual response latency without replacing grounded answers with canned responses. Existing demo data and API keys must be preserved.

## Evidence on Hand

The existing profile, graph, and chunk index live under data/twin. Display real returned data and measured status; do not invent scores, activity, or speed claims.

## Product Principles

- Conversation and evidence stay easy to reach.
- Preserve existing session history and API contracts.
- Show loading and failure clearly and allow recovery.
- Optimize measured bottlenecks before adding infrastructure.