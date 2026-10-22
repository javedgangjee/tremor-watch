# Python reference

The ParaDigMa toolbox runs here as the reference that the C port must match. Every command runs from the repo root.

## Make the venv

The venv needs Python 3.13. The toolbox's model file loads only with scikit-learn below 1.6.1, and requirements.txt pins 1.6.0.

```
python3.13 -m venv reference/.venv
reference/.venv/bin/pip install -r reference/requirements.txt
```

## Download and check PADS

PADS 1.0.0 is about 735 MB. It goes into data/pads/, and git never tracks it. The download needs wget, which Homebrew installs with `brew install wget`.

```
wget -r -N -c -np -nH --cut-dirs=3 -P data/pads https://physionet.org/files/parkinsons-disease-smartwatch/1.0.0/
(cd data/pads && sed 's/ /  /' SHA256SUMS.txt | shasum -a 256 -c --quiet -)
```

The check prints nothing when every file matches. SHA256SUMS.txt puts one space between the hash and the name, and macOS shasum needs two, so sed adds the second space.

PhysioNet takes about 2 seconds to answer each request, so wget needs about 7 hours for the 10,318 recordings. A faster way is to stop wget after it fetches SHA256SUMS.txt and fetch the missing files 8 at a time with curl. On 22 October 2026 this took about 4 hours.

```
(cd data/pads && awk '{print $2}' SHA256SUMS.txt | while read -r f; do [ -f "$f" ] || echo "$f"; done \
  | xargs -P 8 -I{} curl -sS --fail --retry 3 --create-dirs -o {} https://physionet.org/files/parkinsons-disease-smartwatch/1.0.0/{})
```

PhysioNet resets some connections, so a few files can come back missing or partial. Run the check afterwards. If a file fails it, delete that file and run the curl command again.

## Run the scripts

These five scripts compare the plain rebuild in plain_detector.py with the toolbox on made-up signals. The plan's Measured so far section gives their results.

```
reference/.venv/bin/python reference/compare.py
reference/.venv/bin/python reference/rate_test.py
reference/.venv/bin/python reference/latency_test.py
reference/.venv/bin/python reference/spline_test.py
reference/.venv/bin/python reference/demo_test.py
```

pads_counts.py runs the toolbox on every PADS recording. It writes pads_windows.csv, pads_counts.csv, and pads_counts.md to reference/results/. The `--data` option sets the PADS folder, and the `--out` option sets the output folder.

```
reference/.venv/bin/python reference/pads_counts.py
```

The tests for pads_counts.py need the toolbox, so they run in this venv.

```
reference/.venv/bin/python -m pytest tests/reference -q
```

## Credits

The tremor detector comes from ParaDigMa by the Radboud Parkinson's group, which has an Apache 2.0 licence. The source paper is Timmermans and colleagues, npj Parkinson's Disease, 2025.

The test data is PADS, which has a non-commercial licence. Cite all three of these works when you use it.

- The dataset citation is Varghese, J., Brenner, A., Plagwitz, L., van Alen, C., Fujarski, M., & Warnecke, T. (2024). PADS - Parkinsons Disease Smartwatch dataset (version 1.0.0). PhysioNet. RRID:SCR_007345. https://doi.org/10.13026/m0w9-zx22
- The original publication is Varghese, J., Brenner, A., Fujarski, M., van Alen, C.M., Plagwitz, L., & Warnecke, T. (2024). Machine Learning in the Parkinson's disease smartwatch (PADS) dataset. npj Parkinsons Dis. 10, 9. https://doi.org/10.1038/s41531-023-00625-7
- The standard PhysioNet citation is Pollard, T., Moody, B. E., Lehman, L., Gow, B., Fernandes, C., Xie, C., Johnson, A., Mark, R. G., & Heldt, T. (2026). PhysioNet as a global platform for biomedical research. Nature Health. https://doi.org/10.1038/s44360-026-00096-z
