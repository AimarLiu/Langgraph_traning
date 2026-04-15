# LangGraph Learning Curriculum

## Badges

> Replace `AimarLiu <OWNER>` and `Langgraph_traning <REPO>` with your GitHub repository path after push.

[![Python CI](https://github.com/AimarLiu/Langgraph_traning/actions/workflows/pytest.yml/badge.svg)](https://github.com/AimarLiu/Langgraph_traning/actions/workflows/pytest.yml)

This repository is a hands-on LangGraph training course that guides you from a minimal tool-using agent to a production-oriented agent system.  
Through phased exercises, you will learn core agent patterns such as stateful graph design, tool-calling loops, checkpoint persistence, human-in-the-loop control, streaming, RAG integration, async execution, API deployment, and evaluation/regression workflows.

## Quick Start

1. Create and activate a Python 3.11 environment.
2. Install dependencies and the local package:

```powershell
py -3.11 -m pip install -r Docs/requirements.txt
py -3.11 -m pip install -e .
```

3. Run checks:

```powershell
py -3.11 -m ruff check src tests
py -3.11 -m pytest -q
```

4. Try key practice scripts:

```powershell
py -3.11 practice_04_agent_graph.py
py -3.11 practice_14_fastapi_agent.py
py -3.11 practice_15_eval_smoke.py
```

## Project Structure

- `src/langgraph_learning/`: core learning modules (graphs, tools, pipelines).
- `src/api/`: FastAPI app, routes, schemas, and settings.
- `evaluation/datasets/`: golden datasets for evaluation/regression.
- `Docs/`: setup notes, environment docs, and implementation references.
- `practice_*.py`: phase-by-phase runnable exercises.
- `TODO.md`, `TODO_phase2.md`, `TODO_phase3.md`: staged curriculum checklists.
- `IMPL.md`: implementation log and change history.

## Learning Roadmap (Phase A to Phase P)

### Phase A: Single-turn Tool Basics
- [x] **A1** Complete a single user message -> model response script (`invoke`).
- [x] **A2** Define one `@tool` and manually call it once to verify output format.
- [x] **A3** Use `bind_tools`, parse tool calls, execute the tool, and feed a `ToolMessage` back (manual one-loop flow).

### Phase B: LangGraph Agent Loop ("think -> use tool -> answer")
- [x] **B1** Define `AgentState` with `messages` using `Annotated[..., add_messages]`.
- [x] **B2** Implement `call_model` node with model + `bind_tools`.
- [x] **B3** Implement `run_tools` node to execute `tool_calls` and return `ToolMessage`s.
- [x] **B4** Add conditional edges: loop to tools when needed, otherwise end; set max steps/recursion guard.

### Phase C: More Task-agent-like Behavior
- [x] **C1** Add a second tool and let the model choose between tools.
- [x] **C2** Add tool input validation and timeout/exception handling.
- [x] **C3** (Optional) Add LangSmith or custom logging for tool decisions and parameters.

### Phase D: Reusable Project Structure
- [x] **D1** Split tools and graph definitions into reusable module directories.
- [x] **D2** Document env setup and run instructions; keep dependency docs updated.

### Phase E: Persistence and Thread Continuity (Checkpoint)
- [x] **E1** Compile graph with a checkpointer (`MemorySaver` or `SqliteSaver`).
- [x] **E2** Use `configurable.thread_id` to continue state across turns.
- [x] **E3** (Optional) Understand state history/time-travel checkpoint concepts.

### Phase F: Human-in-the-loop (HITL)
- [x] **F1** Add an interruption point before sensitive tool execution.
- [x] **F2** Resume with `Command` (approve / reject / edit parameters).
- [x] **F3** (Optional) Record approver and approval metadata in state.

### Phase G: Streaming
- [x] **G1** Replace `invoke` with `stream` and inspect graph update events.
- [x] **G2** (Optional) Compare `messages` / `custom` stream modes.
- [x] **G3** Verify streamed flows are traceable (e.g., LangSmith trace alignment).

### Phase H: State Expansion (Beyond `messages`)
- [x] **H1** Extend state fields (`user_id`, `locale`, `pending_tool_args`, etc.).
- [x] **H2** Apply reducers for list/merged fields to avoid unintended overwrite.
- [x] **H3** (Optional) Add message trimming to control token usage/cost.
- [x] **H4** (Extended) Add `filter_messages` + `trim_messages` preprocessing strategy.

### Phase I: Subgraphs or Advanced Routing
- [x] **I1** Split workflow into modular subgraphs (e.g., research/composition).
- [x] **I2** Add intent classification and conditional routing branches.

### Phase J: Intro RAG (Retrieval + Tool)
- [x] **J1** Build a small vector store from internal documents.
- [x] **J2** Wrap retrieval as a `@tool` (`query` -> `similarity_search` -> snippets).
- [x] **J3** Require answer grounding/citations from retrieved content.

### Phase K: Async and Resource Lifecycle
- [x] **K1** Use `await graph.ainvoke(...)` / `astream` and compare with sync behavior.
- [x] **K2** (Optional) Convert I/O-bound tools to async.
- [x] **K3** Clarify checkpointer lifecycle in long-running services.

### Phase L: HTTP Wrapper (Minimal API)
- [x] **L1** Expose `POST /chat` via FastAPI.
- [x] **L2** Pass `thread_id` / optional `user_id` into `config["configurable"]`.
- [x] **L3** (Optional) Add `GET /health` + `pydantic-settings` without leaking secrets.
- [x] **L4** (Optional) Upgrade model node call from sync invoke to async `ainvoke`.

### Phase M: Evaluation and Regression
- [x] **M1** Create a small golden dataset (5-10 examples).
- [x] **M2** (Optional) Add LangSmith dataset/evaluation or LLM-as-judge.
- [x] **M3** Run smoke checks via pytest or script.

### Phase N: Advanced RAG Pipeline (Choose One Main Track)
- [ ] **N1** Add reranking or hybrid retrieval to the current Chroma flow.
- [ ] **N2** (Optional) Add query rewriting / multi-query.
- [ ] **N3** Keep answer traceability/grounding.

### Phase O: Supervisor and Multi-capability Composition (Lightweight Multi-agent)
- [ ] **O1** Add a supervisor node for task judgment and routing.
- [ ] **O2** (Optional) Share a subset of state across two specialist subgraphs.
- [ ] **O3** Document boundaries between single-agent and multi-agent design.

### Phase P: (Optional) Long-term Memory Across Threads
- [ ] **P1** Study the official Store concept.
- [ ] **P2** Implement cross-thread preference write/read flow.

## How to Continue from Here

- If you are new to this repo, start with `practice_01.py` to `practice_04_agent_graph.py` (Phase A/B baseline).
- If you want production-oriented capability, continue with `practice_13_async_agent.py`, `practice_14_fastapi_agent.py`, and `practice_15_eval_smoke.py` (Phase K/L/M).
- If you want deeper architecture practice, continue Phase N/O/P for advanced RAG, supervisor routing, and long-term memory.
- Keep `TODO.md`, `TODO_phase2.md`, `TODO_phase3.md`, and `IMPL.md` updated whenever a phase is completed.
