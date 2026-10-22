# Feature 2 plan: Python reference

The steps run in this order. Step 5 downloads 735 MB, and step 8 runs the toolbox on about 10,300 files.

1. Add data/, reference/.venv/, __pycache__/, and .pytest_cache/ to .gitignore.

2. Move the six scripts with `git mv` from context/ to reference/. The files are plain_detector.py, compare.py, rate_test.py, latency_test.py, spline_test.py, and demo_test.py. In compare.py, rate_test.py, latency_test.py, spline_test.py, and demo_test.py, change only the import line to `from plain_detector import build_tables, detect`.

3. Make the venv with `python3.13 -m venv reference/.venv`. Install paradigma==1.1.2, scikit-learn==1.6.0, and pytest into it. Write `pip freeze` to reference/requirements.txt. Then delete the venv, make it again from reference/requirements.txt, and confirm that the install succeeds.

4. Run reference/compare.py and the four other scripts in the venv, and check the model file's hash. This step changes no repo files, and validation.md records the output.

5. Download PADS 1.0.0 into data/pads/ with `wget -r -N -c -np -nH --cut-dirs=3 -P data/pads https://physionet.org/files/parkinsons-disease-smartwatch/1.0.0/`. Check every file against data/pads/SHA256SUMS.txt.

6. Write reference/pads_counts.py. It follows the user's Python rules, so it uses type hints, pathlib, and logging, and it has no loop over single readings.
   - It reads the groups from data/pads/preprocessed/file_list.csv.
   - For each file in data/pads/movement/timeseries/, it reads the three gyroscope columns, converts them with paradigma.util.convert_units_gyroscope(data, "rad/s"), cuts the first 50 rows, and runs extract_tremor_features and detect_tremor with the default TremorConfig.
   - It logs each missing or unreadable file and counts it, and it stops on any other error.
   - It writes reference/results/pads_windows.csv, reference/results/pads_counts.csv, and reference/results/pads_counts.md.
   - It takes `--data` with a default of data/pads and `--out` with a default of reference/results.

7. Write tests/reference/test_pads_counts.py with the cases in validation.md check 4. Run it, and fix pads_counts.py until every case passes.

8. Run reference/pads_counts.py on all of PADS and commit nothing. The user reviews the three result files.

9. Write reference/README.md. It gives the commands for steps 3, 5, and 8, the commands that run each script, and the PADS and ParaDigMa credit lines.

10. Update specs/tech-stack.md. Add that the five scripts changed their import line in feature 2 and nothing else. Add that PADS 1.0.0 lives in data/pads/ and is never committed. Add pads_counts.py and its results to the reference list.

11. Set the status of feature 2 to in progress in specs/roadmap.md. This step is done in plan mode.
