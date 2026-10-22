# Feature 2 requirements: Python reference

## From the project documents

1. ParaDigMa 1.1.2 is installed in its own venv. This comes from the plan's Build order step 1 and its Test data section.
2. The venv uses Python 3.13 and scikit-learn 1.6.0, because the toolbox's model file needs scikit-learn below 1.6.1. This comes from the plan's Measured so far section and from specs/tech-stack.md.
3. The pinned Python requirements live in reference/. This comes from the plan's Repo layout section.
4. reference/ holds plain_detector.py, compare.py, rate_test.py, latency_test.py, spline_test.py, and demo_test.py. They move there from context/. This comes from the plan's Repo layout section and the roadmap entry for feature 2.
5. reference/compare.py runs and shows that the plain rebuild still matches the toolbox. The plan's Measured so far section gives the expected results. This comes from Build order step 1.
6. The toolbox runs on every PADS task, and the result is how often it fires on each task in each group. This comes from Build order step 2.
7. The groups are Parkinson's, other movement disorder, and healthy. This comes from the plan's Test data section and its What you deliver section.
8. PADS rotation is converted from radians per second to degrees per second with the toolbox's own function. In ParaDigMa 1.1.2 this function is paradigma.util.convert_units_gyroscope. This comes from the plan's Test data section.
9. The first half second of each recording is cut. At 100 readings a second this is the first 50 rows. This comes from the plan's Test data section.
10. PADS runs at 100 readings a second without conversion. This comes from the plan's Test data section.
11. The counts are saved as the reference the C port must reproduce. This comes from Build order step 2.
12. The PADS credit lines name Varghese and colleagues, npj Parkinson's Disease, 2024, and the citation that the PhysioNet page asks for. This comes from the plan's Test data section.

## Not covered by the project documents

The user decided items 13 to 16 on 21 October 2026.

13. In each of the five scripts that import plain_detector, the line `from context.plain_detector import build_tables, detect` becomes `from plain_detector import build_tables, detect`. No other line in the scripts changes. specs/tech-stack.md records this exception.
14. The count script is reference/pads_counts.py. It writes reference/results/pads_counts.csv and reference/results/pads_counts.md, and both files are committed.
15. PADS 1.0.0 is downloaded to data/pads/, and .gitignore leaves data/ out.
16. The counts cover both wrists. Each task and group has a row for the left wrist, the right wrist, and both wrists together.

Items 17 to 25 are proposals. They need the user's approval with the plan.

17. The venv is reference/.venv/, and .gitignore leaves it out. reference/requirements.txt pins every package in the venv to an exact version, including pytest.
18. reference/README.md gives the commands that make the venv, download PADS, and run each script.
19. The group comes from the label column of data/pads/preprocessed/file_list.csv. Label 0 is healthy, label 1 is Parkinson's, and label 2 is other movement disorder. Label 2 holds the PADS conditions Other Movement Disorders, Essential Tremor, Atypical Parkinsonism, and Multiple Sclerosis.
20. The script reads the raw files in data/pads/movement/timeseries/. Their names follow `{id}_{task}_{wrist}.txt`. The 11 tasks are Relaxed, RelaxedTask, StretchHold, LiftHold, HoldWeight, PointFinger, DrinkGlas, CrossArms, TouchIndex, TouchNose, and Entrainment. Relaxed and RelaxedTask are the two rest tasks.
21. The script runs each file on its own through extract_tremor_features and detect_tremor with the default TremorConfig. It gives the toolbox a time column of row number divided by 100 after the cut, and it does not call preprocess_imu_data. This keeps the input the same as the C replay program will see.
22. A window fires when the toolbox's pred_tremor_checked is 1. Each count row gives the number of windows, the number that fired, and the share that fired.
23. The script also writes reference/results/pads_windows.csv with one row per window. Each row holds the subject, group, task, wrist, window number, probability, low-frequency sum, peak frequency, arm at rest answer, and tremor answer. It is committed, because feature 4 can compare the C answers with it window by window.
24. reference/results/pads_counts.md states the ParaDigMa and scikit-learn versions, the PADS version, the SHA-256 hash of the toolbox's model file, the number of files read and missing, the date of the run, and that the patient columns are not a hit rate.
25. The unit tests for pads_counts.py are in tests/reference/test_pads_counts.py and run with pytest in the reference venv. They need the toolbox, so they are not one of the commit checks in feature 7.
