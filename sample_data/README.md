# Sample data (synthetic)

Everything here is invented for demos and tests. No real people, no real health data.

| Path | What it is | Used by |
|---|---|---|
| [`demo_users.json`](demo_users.json) | Three demo profiles (vegetarian/balanced, vegan/weight-management, general/fitness) with `example.com` emails and **no passwords** | [`scripts/seed_demo_data.py`](../scripts/seed_demo_data.py), tests |
| [`images/`](images) | Two illustrated meal images (a poha bowl and a lunch thali), drawn as SVG and exported to PNG | Seeding, screenshots, manual upload testing |
| [`exports/`](exports) | Plans exported by the running app as JSON and text, for the vegetarian and vegan demo users | Shows the API's output format without running anything |

Load the demo users into a running API:

```bash
python scripts/seed_demo_data.py                          # local
python scripts/seed_demo_data.py --base-url https://…     # a deployment
```

Set `DEMO_PASSWORD` to choose the password. Otherwise a random one is generated and printed
once.
