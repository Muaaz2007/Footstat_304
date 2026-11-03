# Market value data limitation and strategy

## 1. The issue we faced

The project is intended to estimate a football player's market value from player attributes and then compare that estimate with the player's recorded value. The dataset used in this project is `fifa_players.csv`.

A practical limitation of this dataset is that it does not contain a clean, authoritative, live market value for every player. The recorded market value in the dataset is treated as the available reference value, but it is not a complete or perfectly accurate representation of a player's current market worth. Some players do not have a recorded value at all, and for others the recorded value may reflect a snapshot rather than a continuously updated market price.

This means we could not simply treat the dataset's recorded value as the true market value and ignore the uncertainty around it.

## 2. What we did instead

Because a fully accurate live market value was not available, we adopted a **threshold-based buffer/tradeoff strategy** around the model's predicted value.

The basic idea is:

- The AI model predicts a market value for a player based on player attributes.
- That predicted value is compared with the recorded value available in the dataset.
- Instead of treating any small difference as meaningful, a buffer is applied so that only differences larger than a defined tolerance are used to assign an evaluation category.
- A player is labelled **Potentially Undervalued**, **Fairly Valued**, or **Potentially Overvalued** relative to the model's estimate, using that buffer.

In other words, the evaluation does not assume the recorded value is exact. It uses a tradeoff: the model's estimate is taken as the reference point, and the recorded value is compared against it within a tolerance band.

## 3. Why this strategy was chosen

This approach was chosen for two main reasons.

First, the goal of the project is not to determine the objectively correct market value of a player. The project is about building a system that uses AI to estimate market value and then presents a comparison between the estimate and the available recorded value. The evaluation is therefore an indication based on the model, not a final real-world valuation.

Second, the dataset limitation meant that a stricter approach would have been misleading. If we had presented small differences as if they were precise market judgments, the system would have implied more certainty than the data supports. The buffer/tradeoff strategy reflects that uncertainty more honestly and keeps the system's output interpretable.

## 4. How the strategy is used in the system

The current prototype uses the following general process:

1. Load and clean the dataset.
2. Build model features from player attributes.
3. Train and compare AI techniques.
4. Use the selected model to estimate market value.
5. Compare the predicted value with the recorded value.
6. Apply a threshold/buffer rule to assign an evaluation category.

Where the dataset does not include a recorded value, the system indicates that no comparison is possible for that player rather than forcing a misleading valuation.

## 5. What this means for the results

The evaluation produced by the system should be read as **model-based indication**, not as a definitive statement of a player's true market value.

A label such as "Potentially Undervalued" means that the model's estimate is meaningfully higher than the recorded value in the dataset, within the tradeoff rule we defined. It does not mean the player is certainly a bargain in a real transfer market.

This is consistent with the project's own scope: the system is an AI-based evaluation support tool, not an official valuation authority.

## 6. Summary

- The dataset does not provide a full or perfectly accurate live market value.
- We used the recorded value as the available reference, with its limitations acknowledged.
- We applied a threshold/buffer tradeoff around the predicted value to decide the evaluation category.
- This was the strategy used because of the data limitation, and it was documented rather than hidden.
- The output is an interpretable AI-based indication, not an exact valuation.
