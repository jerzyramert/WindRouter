# WindRouter — Scampi 30 Weather Routing Engine

A Python weather routing tool for the **Scampi 30** yacht. Reads GRIB forecast files, builds a safe-sailing graph, and finds the fastest route using Dijkstra (2D/3D) and VMG optimisation. Results are exported as GPX tracks and a detailed log.

---

## Project structure

```
WindRouter/
├── grib.py            ← routing engine (polars, routing algorithms, I/O)
├── Visualiser.py      ← Tkinter map viewer
├── REQUIREMENTS.md    ← bug list (B-01 … B-30) and feature requirements
└── REFACTORING_PLAN.md ← staged plan for fixing bugs and splitting the codebase
```

---

## Running the engine

```bash
# place your forecast file in the project root, then:
python grib.py
```

Hard-coded defaults in `__main__`: start/target coordinates, GRIB filename (`test.grb2`), output paths. Edit these directly until the CLI is added (Stage 6 of the refactoring plan).

---

## Running the visualiser

```bash
python Visualiser.py
```

Requires Tkinter (standard library). Watches the output directory and reloads GPX/JSON files automatically.

---

## Known bugs

30 documented bugs are listed with locations, descriptions, and affected requirements in `REQUIREMENTS.md`. The staged fix plan is in `REFACTORING_PLAN.md`.

---

## Dependencies

| Package | Use |
|---------|-----|
| `pygrib` | Read GRIB2 forecast files (requires ecCodes system library) |
| `numpy` | Grid arithmetic |
| `scipy` | `RegularGridInterpolator` for polar table lookup |

### Install ecCodes (required for pygrib)

**Ubuntu/Debian:**
```bash
sudo apt-get install libeccodes-dev
pip install pygrib numpy scipy
```

**macOS (Homebrew):**
```bash
brew install eccodes
pip install pygrib numpy scipy
```

**Windows:** Use WSL or a conda environment with `conda install -c conda-forge pygrib`.
