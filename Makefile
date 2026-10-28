# `make check` runs these targets in order and stops at the first failure.
# None of them needs the toolbox.
#
#   laptop   builds core/ and replay and runs the C unit tests.
#   hash     compares the model file's SHA-256 with DET_MODEL_SHA256 in
#            core/detector_tables.h.
#   viewer   runs the recording viewer's unit tests in viewer/test/ with Node.
#            They need no network and no installed packages.
#   firmware builds the watch firmware in firmware/ with ESP-IDF.
#
# The viewer's capture checks run the real Electron app, so they need
# `npm --prefix viewer ci` and a screen. They stay out of `make check`, and
# `make viewer-smoke` runs them. OUT names the folder for their PNG and JSON
# files, and with no OUT the smoke script makes a temporary folder.
#
# `make viewer-start` opens the recording viewer. FILE names a saved
# recording, and BOOT picks one boot in it, as in
# `make viewer-start FILE=session.txt.gz BOOT=2565193163`. With no FILE the
# app opens empty, and File > Open picks a recording.
#
# Both viewer targets run `npm --prefix viewer ci` first when
# viewer/node_modules is missing or older than viewer/package-lock.json.
# The install and the first start need the network.
#
# `make python` runs the pytest tests in tests/ with the reference venv, which
# holds the toolbox. They include the full PADS match, the check that the
# detector tables regenerate from the model file, the laptop tools, and the
# judges of the watch logs. Some need the build that `make laptop` makes, and
# the whole run takes several minutes. PYTHON names another interpreter.
#
# `make full` runs `make check` and then `make python`.

MODEL ?= tests/model/tremor_detection_clf_package.pkl
TABLES ?= core/detector_tables.h
IDF_ACTIVATE ?= $(HOME)/.espressif/tools/activate_idf_v6.1.sh
PYTHON ?= reference/.venv/bin/python

.PHONY: check laptop hash viewer viewer-start viewer-smoke firmware python full

check: laptop hash viewer firmware

python:
	"$(PYTHON)" -m pytest -q tests

full: check python

laptop:
	cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure

hash:
	@model=$$(shasum -a 256 "$(MODEL)" | cut -d ' ' -f 1); \
	tables=$$(sed -n 's/^#define DET_MODEL_SHA256 "\([^"]*\)".*/\1/p' "$(TABLES)"); \
	echo "model file $(MODEL) has hash $$model"; \
	echo "tables file $(TABLES) has hash $$tables"; \
	if [ -z "$$model" ] || [ -z "$$tables" ] || [ "$$model" != "$$tables" ]; then \
		echo "model hash does not match"; \
		exit 1; \
	fi; \
	echo "model hash matches"

viewer:
	node --test viewer/test/*.test.js

# npm ci writes this file last, so it marks a finished install.
VIEWER_INSTALLED := viewer/node_modules/.package-lock.json

$(VIEWER_INSTALLED): viewer/package-lock.json
	npm --prefix viewer ci

viewer-start: $(VIEWER_INSTALLED)
	npm --prefix viewer start --$(if $(FILE), "$(FILE)")$(if $(BOOT), --boot "$(BOOT)")

viewer-smoke: $(VIEWER_INSTALLED)
	npm --prefix viewer run smoke --$(if $(OUT), --out "$(OUT)")

# The activate script sets IDF_TOOLS_PATH, which export.sh needs here. It also
# makes idf.py a shell function that make cannot call, so this runs
# $IDF_PATH/tools/idf.py directly.
firmware:
	if ! command -v idf.py >/dev/null 2>&1; then . "$(IDF_ACTIVATE)" >/dev/null; fi; "$$IDF_PATH/tools/idf.py" -C firmware build
