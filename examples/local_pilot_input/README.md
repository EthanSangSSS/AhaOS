# Sample Input

This folder contains safe sample files for `scripts/local_pilot.py`. These files represent raw inputs (such as memory atoms and open loops) fed into the AhaOS memory incubator to generate candidate aha moments and latent links.

Run:

```bash
python3 scripts/local_pilot.py \
  --input-dir examples/local_pilot_input \
  --work-dir /tmp/ahaos-local-pilot \
  --report-dir /tmp/ahaos-local-pilot-reports \
  --top-k 3
```
