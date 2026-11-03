# Footstat_304 - AI-Based Football Player Performance and Market Value Evaluation System

This repository contains the ICT304 group project for an AI-based football player performance and market value evaluation system.

The project is not just a machine-learning model. It is a system that combines data processing, AI-based market value prediction, comparison with recorded value, player evaluation, and a user-facing dashboard.

## What the system does

The system takes football player data, processes it, and uses an AI model to estimate a player's market value from player attributes. It then compares the estimated value with the recorded value available in the dataset and presents an evaluation to the user.

The evaluation indicates whether a player appears potentially undervalued, fairly valued, or potentially overvalued relative to the model's estimate.

The overall workflow is:

**Dataset -> Data Processing -> Feature Selection -> AI Market Value Prediction -> Predicted Market Value -> Comparison with Recorded Market Value -> Player Evaluation -> Dashboard**

## Main parts of the system

The system is organised into a few logical parts:

- **Data** - the football player dataset and any processed data used by the system
- **AI subsystem** - data cleaning, feature preparation, model training, model comparison, prediction, and evaluation
- **Backend/data layer** - the data and service responsibilities that connect the AI output with the rest of the system
- **Frontend** - the user-facing dashboard or interface that presents player information and evaluation results
- **AI core** - the current AI prototype implementation and its supporting outputs

The project folder structure is intended to separate these concerns so that each part can be developed and understood more clearly.

## Folder structure

- `ai-core/` - AI subsystem prototype (offline pipeline): preprocessing, model comparison, prediction, evaluation, outputs
- `ai/` - runtime AI module for predicting a single player on demand
- `backend/` - runtime service: the data access layer and the JSON API the dashboard calls
- `backend/data/` - loading, validation and query logic for the prediction table
- `frontend/` - the dashboard/interface (not built yet)
- `data/` - notes on where the project data lives, see `data/README.md`

## How the AI subsystem fits in

The AI subsystem is one part of the whole system. Its role is to:

- clean and prepare the player data
- select and prepare features
- train and compare candidate AI techniques
- choose a model
- predict market value for players
- compare predicted value with recorded value
- produce an evaluation category

The AI subsystem works mostly offline during development. It produces results that the rest of the system can use at runtime.

During normal dashboard use, the system does not need to retrain the model every time. Instead, the dashboard can use the prepared prediction results from the AI subsystem.

## Market value and the data limitation

A key point in this project is that the dataset does not provide a fully accurate live market value for every player. The recorded value in the dataset is used as the available reference, but it has limitations.

Because of this, the project uses a threshold/buffer tradeoff strategy around the model's predicted value when deciding the evaluation category. This means the system does not treat every small difference as meaningful. Instead, it uses a tolerance-based rule so the evaluation reflects a meaningful comparison rather than noise.

This strategy is documented because it was a response to a real data limitation. Details are in `ai-core/MARKET_VALUE_LIMITATION_AND_STRATEGY.md`.

The evaluation produced by the system should be understood as an **AI-based indication**, not an exact real-world valuation.

## What the dashboard should show

For a selected player, the system is intended to present:

- player information
- relevant player attributes
- recorded market value, where available
- predicted market value
- the difference between predicted and recorded value
- the evaluation result

The AI subsystem exposes this information through a defined interface so the dashboard can use it consistently. That interface is described in `ai-core/INTERFACE_FOR_DASHBOARD.md`.

## Current state of the project

The AI subsystem prototype is the most developed part so far. It includes:

- data preprocessing
- feature preparation
- comparison of two AI techniques
- prediction and evaluation output
- supporting output files

The backend part of the runtime system has now been implemented. It reads the prediction
table produced by the AI subsystem, validates it against the interface contract, and serves
it through a JSON API for the dashboard. It also has a unit test suite.

So the current status is:

- AI subsystem: prototype complete, producing predictions and evaluations
- backend/data layer: implemented and tested
- AI runtime (single-player prediction): implemented, needs the AI dependencies to run
- dashboard/interface: not started

## How to run the AI part

The AI subsystem can be run locally as a prototype. In general, the workflow is:

1. install the Python dependencies
2. prepare the raw dataset
3. run preprocessing
4. run model training and comparison
5. run prediction and evaluation

Exact steps should follow the instructions inside `ai-core/`.

## How to run the backend

The backend reads the prediction table and serves it as JSON. It needs only Python 3.9 or
newer, with nothing to install.

```bash
python -m backend.api                    # http://127.0.0.1:8000
python -m backend.api --port 8080        # different port
python -m backend.api --data some.csv    # different prediction table
```

Useful routes:

- `GET /api/health` - service and data status
- `GET /api/summary` - dataset totals, evaluation counts, top movers
- `GET /api/players?search=messi` - searchable player list
- `GET /api/players/1` - one player's full evaluation

Full route documentation, query parameters and error responses are in `backend/README.md`.

Run the backend tests with:

```bash
python -m unittest discover -s backend/tests -t .
```

## What still needs to be done

From a system point of view, the remaining work is mainly integration and completion:

- finish the dashboard/frontend so users can view player information and evaluation results
- connect the dashboard to the AI output through the defined interface
- decide what belongs in the backend/data layer and implement it
- keep the system description consistent with what the project actually delivers

## Notes on scope

The system is designed as an AI-based evaluation support tool. It is meant to help users analyse players by combining AI prediction with a simple comparison and presentation workflow.

It does not claim to determine the true market value of a player. The results are based on the data available and the model used, and the evaluation should be read in that context.

## Related documents

- `ai-core/MARKET_VALUE_LIMITATION_AND_STRATEGY.md` - explains the market value data limitation and the tradeoff strategy used
- `ai-core/INTERFACE_FOR_DASHBOARD.md` - describes the AI-to-dashboard interface
- `ai-core/README.md` - describes the AI subsystem prototype itself
- `backend/README.md` - backend structure, routes and how to run it
- `ai/README.md` - the runtime single-player prediction module
- `data/README.md` - where each data file lives
- `docs/IMPLEMENTATION_NOTES.md` - what was implemented in the backend, why, and how it was verified
