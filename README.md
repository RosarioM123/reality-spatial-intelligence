# reality-spatial-intelligence

AI-native spatial intelligence pipeline (simplified open-source version).

Ingest a description of physical space — zones (rooms, hallways), entities
(sensors, furniture, robots), and how zones connect — then answer spatial
questions with JSON-serializable results designed for AI systems to consume
directly (as tool calls or via the plain-language `ask` interface).

## Install

Requires Python 3.10+. No third-party dependencies.

```bash
git clone https://github.com/RosarioM123/reality-spatial-intelligence.git
cd reality-spatial-intelligence
pip install -e .
```

## Quickstart

```bash
# Validate the example office world
reality validate examples/office.json

# Ask plain-language spatial questions (answers are JSON)
reality ask examples/office.json "where is printer-1?"
reality ask examples/office.json "what is near reception-desk within 5"
reality ask examples/office.json "nearest equipment to desk-1"
reality ask examples/office.json "how do I get from Office A to Office B?"
reality ask examples/office.json "what zone is at (2, 7)?"

# Lower-level primitives
reality route examples/office.json office-a office-b
reality near examples/office.json 5 4 10 --kind equipment
reality zones examples/office.json
```

Or from Python:

```python
from reality.core.pipeline import SpatialPipeline
from reality.core.queries import ask

pipeline = SpatialPipeline.from_file("examples/office.json")
print(ask(pipeline, "where is printer-1?"))
# {"type": "entity_location", "entity": {...}, "zone_id": "hallway", ...}
```

## World file format

A world is a JSON document with three sections:

```json
{
  "zones": [
    {"id": "lobby", "name": "Lobby", "floor": 0,
     "polygon": [[0,0],[10,0],[10,8],[0,8]]}
  ],
  "entities": [
    {"id": "printer-1", "name": "Printer 1", "kind": "equipment",
     "position": [12,16], "zone_id": "hallway"}
  ],
  "adjacency": {"lobby": ["hallway"], "hallway": ["lobby"]}
}
```

- `zones`: polygonal areas; `polygon` is a list of `[x, y]` (or `[x, y, z]`) points.
- `entities`: things in space; `kind` is a free-form category (sensor, furniture, robot...).
- `adjacency`: which zones connect directly (doors/openings); used for routing.

`reality validate` checks polygons, id references, and adjacency before use.

## Project structure

```
reality/
  config.py        # settings (env-overridable: REALITY_*)
  core/
    models.py      # Point, Zone, Entity, SpatialWorld (+ JSON serde)
    geometry.py    # point-in-polygon, distance, area, bbox, centroid
    pipeline.py    # ingest -> validate -> index -> query (locate/near/route)
    queries.py     # plain-language ask() -> JSON answers
  infra/
    store.py       # save/load worlds as JSON
    cli.py         # `reality` command-line interface
examples/office.json   # sample office floor
tests/                 # pytest suite
```

## Configuration

Environment variables (all optional):

- `REALITY_DATA_DIR` — default directory for world files (default: `data`)
- `REALITY_DEFAULT_RADIUS` — default proximity radius (default: `5.0`)
- `REALITY_MAX_RESULTS` — cap on proximity results (default: `50`)

## Tests

```bash
pytest
```

## Limitations

This is the simplified open-source version: 2D zone geometry (z is carried but
unused by containment tests), a BFS zone-graph router (no obstacle-aware path
planning), regex-based question parsing (not an LLM), and JSON-file persistence
only. Real-time sensor ingestion and 3D meshes are out of scope.
