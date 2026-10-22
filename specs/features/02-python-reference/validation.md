# Feature 2 validation: Python reference

Every command runs from the repo root.

## Automated checks

1. The venv builds from the pinned requirements.
   - The command is `rm -rf reference/.venv && python3.13 -m venv reference/.venv && reference/.venv/bin/pip install -r reference/requirements.txt && reference/.venv/bin/python -c "import sys, importlib.metadata as m; print(sys.version.split()[0], m.version('paradigma'), m.version('scikit-learn'))"`.
   - The expected result is exit code 0 and a line that starts with 3.13 and ends with 1.1.2 1.6.0.

2. The installed model file is the published one.
   - The command is `shasum -a 256 "$(reference/.venv/bin/python -c 'import paradigma, pathlib; print(pathlib.Path(paradigma.__file__).parent / "assets/tremor_detection_clf_package.pkl")')"`.
   - The expected hash is 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e, which is the hash of the file in the ParaDigMa 1.1.2 wheel on PyPI.

3. The plain rebuild still matches the toolbox.
   - The command is `reference/.venv/bin/python reference/compare.py`.
   - The first line says True and 12, with a threshold of about 0.0296.
   - The second line says 37 numbers plus the threshold.
   - The third line says 200 toolbox windows and 200 plain windows.
   - The float64 line gives a largest mfcc difference and a largest prob difference of 1e-12 or less, and the tremor label agrees on 200 of 200 windows.
   - The float32 line gives a largest mfcc difference of 1.5e-06 or less and a largest prob difference of 7e-07 or less, and the tremor label agrees on 200 of 200 windows. These limits come from the plan's Measured so far section.

4. The count script handles PADS files correctly.
   - The command is `reference/.venv/bin/python -m pytest tests/reference -q`.
   - The test cases are below. Each made-up file has the seven PADS columns, which are time, three accelerometer axes in g, and three gyroscope axes in radians per second.
     1. The name 001_RelaxedTask_LeftWrist.txt gives subject 001, task RelaxedTask, and wrist left.
     2. Label 0 gives healthy, label 1 gives Parkinson's, label 2 gives other movement disorder, and label 3 raises ValueError.
     3. A gyroscope row of 1.0, -0.5, and 0.0 radians per second becomes 57.29578, -28.64789, and 0.0 degrees per second, within 0.0001.
     4. A file of 1024 rows keeps 974 rows after the cut, and the first kept row is row 50 of the file.
     5. A still file of 1024 rows gives 2 windows, and a still file of 2048 rows gives 4 windows. A still file is seeded noise of 1 degree per second on each axis plus a 0.3 Hz drift.
     6. A file of 1024 rows with a 5 Hz shake of 200, 70, and 40 degrees per second on the three axes, written in radians per second, gives 2 windows that both fire. This comes from the "firm 5 Hz" case in reference/latency_test.py and the 5 Hz result in the plan's Measured so far section.
     7. The still file from case 5 gives 2 windows that do not fire, and both say the arm is at rest.
     8. A made-up window table for healthy Relaxed has 4 left windows with 1 fired and 4 right windows with none fired. The counts give 0.25 for left, 0.0 for right, and 0.125 for both.
     9. A file list that names a subject with no files gives a missing count of 22 and does not stop the run.
   - The expected result is 9 passed.

5. The other four scripts still run and give the measured results.
   - The commands are `reference/.venv/bin/python reference/rate_test.py`, `reference/.venv/bin/python reference/latency_test.py`, `reference/.venv/bin/python reference/spline_test.py`, and `reference/.venv/bin/python reference/demo_test.py`.
   - Each command exits with code 0.
   - In rate_test.py, the line for 112.1 Hz run at 112 Hz says the tremor label agrees on 98.0% of windows, because 2 of 100 windows differ.
   - In latency_test.py, the 50, 200, 600, and 1500 degrees per second shakes at 5 Hz each give tremor 20/20.
   - In spline_test.py, the line for margin 16 in float32 gives 150 windows, a largest probability gap of 5e-07 or less, and agreement of 100.0%. Its largest value gap is about 0.41 degrees per second. This gap sits in the last 0.05 seconds of the recording, where the toolbox's curve and the block fit end in different ways. Away from the end the gap is about 3.2e-06, as the plan's Measured so far section says. The user agreed this change on 21 October 2026.
   - In demo_test.py, each of the five cases with the forearm resting shows Tremor in 10/10 runs and stays on Tremor for 99% or more of the shake. The 600 degrees per second case gives 99%, which is one window in ten runs. The user agreed this change on 21 October 2026.

6. The count script runs on all of PADS.
   - The command is `reference/.venv/bin/python reference/pads_counts.py`.
   - The expected result is exit code 0 and the three files reference/results/pads_windows.csv, reference/results/pads_counts.csv, and reference/results/pads_counts.md.
   - pads_counts.md gives files read plus files missing as 10318, which is 469 people times 11 tasks times 2 wrists.
   - pads_counts.csv has 99 rows, which is 11 tasks times 3 groups times 3 wrist views.
   - The number of rows in pads_windows.csv equals the number the command below prints. It adds up the whole 4 second windows left in each file after the cut, using the row counts in the observation files.
   - The command is `reference/.venv/bin/python -c "import json, pathlib; print(sum((s['rows'] - 50) // 400 * len(s['records']) for p in pathlib.Path('data/pads/movement').glob('observation_*.json') for s in json.loads(p.read_text())['session']))"`.

7. The repo holds the right files.
   - The command is `git add -A -n . | grep -E '^add .(data/|reference/\.venv/)'; git diff main -M --stat; git diff main -M -- reference/`.
   - The first command prints nothing.
   - The stat shows six renames from context/ to reference/.
   - The diff of reference/ changes exactly one line in each of compare.py, rate_test.py, latency_test.py, spline_test.py, and demo_test.py, and it changes no line in plain_detector.py.

## Manual checks

8. The count report is complete.
   - Open reference/results/pads_counts.md.
   - The expected result is that it states the ParaDigMa version 1.1.2, the scikit-learn version 1.6.0, PADS version 1.0.0, the model file's hash from check 2, the files read and missing, and the date of the run.
   - The expected result is that it states that the patient columns are not a hit rate.
   - The expected result is that its table has a row for each task, group, and wrist view, with the windows, the windows that fired, and the share.

9. The README is complete.
   - Open reference/README.md.
   - The expected result is that it gives the commands to make the venv, download and check PADS, and run each script, and that it gives the ParaDigMa and PADS credit lines with the citation the PhysioNet page asks for.

## Requirement coverage

Requirements 1, 2, 3, and 17 are covered by check 1. Requirement 4 is covered by check 7. Requirement 5 is covered by checks 2 and 3. Requirements 6, 7, 11, 16, and 22 are covered by checks 4, 6, and 8. Requirement 8 is covered by check 4 cases 3 and 6. Requirement 9 is covered by check 4 case 4. Requirement 10 is covered by check 4 case 5. Requirement 12 is covered by check 9. Requirement 13 is covered by checks 5 and 7. Requirement 14 is covered by checks 6 and 7. Requirement 15 is covered by checks 6 and 7. Requirement 18 is covered by check 9. Requirement 19 is covered by check 4 case 2. Requirement 20 is covered by check 4 case 1 and check 6. Requirement 21 is covered by check 4 cases 5 to 7. Requirement 23 is covered by check 6. Requirement 24 is covered by check 8. Requirement 25 is covered by check 4.

## Results

The checks ran on 22 October 2026 on branch feature/02-python-reference at commit 3bf6c35. Every check passed.

1. Check 1 passed. The venv rebuilt from reference/requirements.txt with exit code 0 and printed 3.13.15 1.1.2 1.6.0.
2. Check 2 passed. The model file's hash is 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e.
3. Check 3 passed. The first line gave True, 12, and a threshold of 0.029570, and the second gave 37 numbers plus the threshold. Both sides had 200 windows. In float64 the largest mfcc difference was 3.55e-15 and the largest prob difference was 8.88e-16. In float32 they were 1.24e-06 and 2.02e-07. The tremor label agreed on 200 of 200 windows in both.
4. Check 4 passed. pytest reported 9 passed.
5. Check 5 passed. All four scripts exited with code 0. rate_test.py gave 98.0% for 112.1 Hz run at 112 Hz. latency_test.py gave tremor 20/20 for the 50, 200, 600, and 1500 degrees per second shakes. spline_test.py gave 150 windows, a largest probability gap of 4.50e-07, and 100.0% agreement for margin 16 in float32, with a largest value gap of 0.409 degrees per second. demo_test.py showed Tremor in 10/10 runs for each resting case, and the stays-on share was 100% except 99% for the 600 degrees per second case.
6. Check 6 passed. The script exited with code 0 in 55 seconds. It read 10318 files with 0 missing, pads_counts.csv has 99 rows, and pads_windows.csv has 26264 rows, which equals the number from the observation files. The three result files are the same byte for byte as the committed files.
7. Check 7 passed. git add printed no file in data/ or reference/.venv/. The stat shows six renames from context/ to reference/. Each of the five scripts changes only its import line, and plain_detector.py does not change.
8. Check 8 passed. The user confirmed the count report.
9. Check 9 passed. The user confirmed the README.

Every item in requirements.md has at least one passing check.
