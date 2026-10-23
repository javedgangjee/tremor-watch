# Feature 3 plan: Generated tables

The steps run in this order. Every command runs from the repo root in the reference venv. No step changes a file in reference/ or context/.

1. Write tools/gen_tables.py. It follows the user's Python rules, so it uses type hints, pathlib, and logging, and it lets errors stop the run.
   - It adds reference/ to the import path and calls build_tables() from plain_detector.py for the two Hann windows, the filter table, and the cosine table.
   - It loads the model file with paradigma.classification.ClassifierPackage, as reference/compare.py does. It reads the means and spreads from the scaler, the weights and the offset from the classifier, and the cut-off from the package.
   - It reads the model file's bytes and computes their SHA-256 hash.
   - It stops with an error and writes no file in the three cases in requirement 18.
   - It writes each model number as a `double` literal with the shortest text that gives back the same float64 value. It writes each table value as a `float` literal with the shortest text that gives back the same float32 value. Every literal is a valid C floating constant, and every `float` literal ends in `f`.
   - It writes the header in the layout of requirements 14, 20, and 21, with one array row per text line for the two tables with rows.
   - It takes `--out` with a default of core/detector_tables.h and `--model` with a default of the installed toolbox's assets/tremor_detection_clf_package.pkl. It logs the path it wrote and the hash.

2. Run `reference/.venv/bin/python tools/gen_tables.py` to make core/detector_tables.h. Read the header once and confirm that the comment and the layout match requirements 14, 20, and 21.

3. Write tests/tools/dump_tables.c. It includes core/detector_tables.h and prints each macro and each value on its own line, as a name, an index, and the value in C's `%a` hexadecimal float form. The `%a` form is exact, so Python reads back the same bits with float.fromhex.

4. Write tests/tools/test_gen_tables.py with the cases in validation.md check 1. It compiles dump_tables.c once per session into a temporary folder with `cc -std=c11 -Wall -Wextra -Werror -pedantic -ffp-contract=off -I core`, and it reads the printed values into numpy arrays. Cases 12 and 13 build their 200 windows in the same way as reference/compare.py, so the test copies that generator and does not import compare.py.

5. Run `reference/.venv/bin/python -m pytest tests/tools -q`. If a case fails, fix tools/gen_tables.py, make the header again, and run the tests again. Never change plain_detector.py, the model file, or a model number to make a case pass. If a case can pass only that way, stop and report it.

6. Update specs/tech-stack.md. Under Shared C library, add that the generated tables are in core/detector_tables.h and that `reference/.venv/bin/python tools/gen_tables.py` makes them. Add that the model numbers are 64-bit values and the tables are 32-bit values. Under Reference and laptop tools, add that the tests for gen_tables.py need the toolbox and run in the reference venv.

7. Set the status of feature 3 to in progress in specs/roadmap.md. This step is done in plan mode.
