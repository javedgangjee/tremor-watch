# `make check` runs these targets in order and stops at the first failure.
# None of them needs the toolbox.
#
#   laptop   builds core/ and replay and runs the C unit tests.
#   hash     compares the model file's SHA-256 with DET_MODEL_SHA256 in
#            core/detector_tables.h.
#   firmware builds the watch firmware in firmware/ with ESP-IDF.
#
# The full PADS match needs the toolbox, so it is not run here.

MODEL ?= tests/model/tremor_detection_clf_package.pkl
TABLES ?= core/detector_tables.h
IDF_ACTIVATE ?= $(HOME)/.espressif/tools/activate_idf_v6.1.sh

.PHONY: check laptop hash firmware

check: laptop hash firmware

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

# The activate script sets IDF_TOOLS_PATH, which export.sh needs here. It also
# makes idf.py a shell function that make cannot call, so this runs
# $IDF_PATH/tools/idf.py directly.
firmware:
	if ! command -v idf.py >/dev/null 2>&1; then . "$(IDF_ACTIVATE)" >/dev/null; fi; "$$IDF_PATH/tools/idf.py" -C firmware build
