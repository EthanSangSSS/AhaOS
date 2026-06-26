# Sample Input

This folder contains safe sample files for `scripts/pilot.py`. These files represent raw inputs (such as memory atoms and open loops) fed into the AhaOS memory incubator to generate candidate aha moments and latent links.

Run:

```bash
python3 scripts/pilot.py \
  --input-dir examples/pilot_input \
  --work-dir /tmp/ahaos-work \
  --report-dir /tmp/ahaos-reports \
  --top-k 3
```
