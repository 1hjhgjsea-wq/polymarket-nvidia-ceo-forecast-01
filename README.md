# polymarket-nvidia-ceo-forecast-01

Entry for make.fun's `polymarket-nvidia-ceo-forecast-01`: forecast five quantiles of every
Polymarket "Next CEO of NVIDIA?" market's Yes price at each of the 240 minutes after a checkpoint.

`main.py` (Python 3.13, standard library only, no network) is run once per case and writes
`/output/<case>.out`.

Method: per-market empirical quantiles of the h-minute move over the trailing 18 hours, scaled by
the ratio of the last hour's volatility to the last day's (volatility clusters), with a mild pull
toward the trailing median and a small shrink of the empirical 5%/95% tails.

Practice pinball loss: **0.320323** (house baseline 0.363589). Every one of the six practice cases
is below the baseline. Deterministic: two runs of a case are byte-identical.

```
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
