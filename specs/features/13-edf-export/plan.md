# Feature 13 plan: EDF export

The steps run in this order. Every command runs from the repo root. The tool and its tests run in the reference venv with `reference/.venv/bin/python` after the C build with `cmake -S . -B build && cmake --build build`. The Python code follows the user's Python rules: type hints on every signature, pathlib, logging and no print, no bare `except Exception`, and numpy with no Python loop over samples.

No step changes a file in firmware/, core/, reference/ apart from requirements.txt, viewer/, context/, or tests/firmware/. In tools/ only compare_session.py changes, and only to import the moved readers. Never change a case or a limit in validation.md to make it pass. If a case can pass only that way, stop and report it.

1. Install the test reader as in requirement 31.
   - Add `edfio==0.4.18` to reference/requirements.txt in its sorted place.
   - Run `reference/.venv/bin/pip install edfio==0.4.18`. It needs the network, so it may need the sandbox turned off. Check with `reference/.venv/bin/pip check` that numpy is still 2.5.4 and nothing else changed.

2. Write tools/recording_text.py as in requirement 15.
   - Move READ_CHUNK, read_gzip_text(), read_recording(), FORMAT_DOC, RECORD_LETTERS, and record_patterns() from tools/compare_session.py with no change to their code.
   - In tools/compare_session.py, import those names from recording_text and delete the moved code. `cs.read_recording` and the other names used by tests/tools/test_compare_session.py must still work.
   - Run `reference/.venv/bin/python -m pytest tests/tools/test_compare_session.py -q`, which must pass as before.

3. Write tools/edfplus.py as in requirements 14, 21, 22, 26, 27, and 29. It holds no watch knowledge.
   - `class EdfError(ValueError)` for a value the format cannot hold.
   - `@dataclass(frozen=True) class SignalSpec` with label, transducer, unit, physical_min, physical_max, digital_min, digital_max, prefiltering, and samples_per_record. The physical and digital limits are text, so 1023.875 is written exactly.
   - `@dataclass(frozen=True) class Annotation` with onset_us, duration_us or None, and text.
   - `@dataclass(frozen=True) class EdfHeader` with patient, recording, startdate, starttime, and the record duration in whole seconds.
   - `seconds_text(us: int, signed: bool) -> str` gives the text of requirement 27 with integer maths only.
   - `tal_bytes(onset_us: int, duration_us: int | None, texts: Sequence[str]) -> bytes` and `timekeeping_tal(onset_us: int) -> bytes`. A text holding byte 0, 20, or 21 raises EdfError.
   - `field(value: str, width: int) -> bytes` pads with spaces and raises EdfError when the value is too long or holds a byte outside 32 to 126.
   - `header_bytes(header: EdfHeader, signals: Sequence[SignalSpec], annotation_samples: int, records: int, continuous: bool) -> bytes` writes the 256-byte main header and 256 bytes for each signal, with the annotation signal last.
   - `annotation_block(record_onsets_us: np.ndarray, annotations: Sequence[Annotation]) -> np.ndarray` puts each annotation in its record with np.searchsorted and gives a uint8 array of shape (records, width) with even width, as in requirement 29.
   - `is_continuous(record_onsets_us: np.ndarray, duration_us: int) -> bool` and a check that raises EdfError when record onsets do not rise by at least the duration.
   - `edf_bytes(header, signals, digital: np.ndarray, record_onsets_us: np.ndarray, annotations) -> bytes` takes digital samples of shape (records, signals, samples) as int16, builds every record at once with numpy, and joins the header and the records.
   - `write_new(path: Path, data: bytes) -> None` opens the path in mode `xb`, writes, and removes the file when the write fails.

4. Write tools/export_edf.py as in requirements 1 to 13 and 16 to 30.
   - A module docstring that gives the command, the venv, the file naming, and where the rules live.
   - `class ExportError(Exception)` for a problem that stops the run with exit code 1.
   - Dataclasses for one boot's events: BootEvents with the boot ID, the firmware version, the last S line of each stretch, the W answers keyed by stretch and window, the sensor fault count, the F lines, the D lines, the first good CLOCK line, the bad CLOCK count, and the bad line count. A Segment holds a replay stretch's number, t0, and its samples as a (n, 3) float array.
   - `read_events(lines: Sequence[str]) -> list[BootEvents]` reads the record lines with the patterns from recording_text.record_patterns() and the CLOCK line with its own pattern. It applies requirement 8 and raises ExportError for a boot ID that comes back after another boot.
   - `run_replay(replay: Path, lines: Sequence[str]) -> tuple[dict[tuple[int, int], int], np.ndarray, str]` runs replay with a temporary samples file in a TemporaryDirectory and gives the t0 of each (boot, stretch), the samples, and replay's summary line. It raises ExportError when replay is missing or exits with a code other than 0.
   - `segments_for(boot_id: int, t0s, samples) -> list[Segment]` groups the samples of one boot with numpy and checks requirement 19.
   - `record_onsets(segments) -> np.ndarray` and `digital_records(segments) -> tuple[np.ndarray, int]`, which gives the int16 records and the clipped count as in requirements 20 and 23.
   - `file_start(first_record_us: int, clock) -> tuple[int, date | None, time | None]` gives the file start on the timer and the header's date and time as in requirements 24 and 25.
   - `annotations_for(events: BootEvents) -> tuple[list[edfplus.Annotation], dict[str, int]]` builds the annotations of requirement 28 and their counts by kind.
   - `header_for(events, start_date, start_time) -> edfplus.EdfHeader` as in requirements 25 and 26, and the four SignalSpec values of requirements 22 and 23 as constants.
   - `export_boot(events, segments) -> tuple[bytes, BootSummary]` joins these steps for one boot.
   - `output_path(recording: Path, out_dir: Path | None, boot_id: int) -> Path` as in requirement 17.
   - `parse_args()` and `main(argv: list[str] | None = None) -> int`. main reads the file with recording_text.read_recording(), turns a missing file, a bad gzip file, and an OSError into ExportError, warns when the file was cut short, builds every boot's bytes, checks that no output path exists, writes the files, and logs the summary of requirement 30.

5. Write tests/tools/test_export_edf.py with the cases of validation.md check 1, in the same order and with the same numbers.
   - It imports export_edf and edfplus from tools/, recording_maker from tests/replay/, and edfio.
   - It holds its own small readers: one for the time-keeping TALs and the place of each annotation in the raw bytes, and one for the W, S, F, D, and CLOCK lines of a recording. They must not import from export_edf or edfplus, so the tests do not check the writer with its own reader.
   - Module scoped fixtures export each committed recording once into a temporary folder and run replay once on it for the expected samples.

6. Add the `edf` target to the Makefile as in requirement 16. It runs `cmake --build build --target replay` and then `"$(PYTHON)" tools/export_edf.py "$(FILE)"` with `--out-dir "$(OUT_DIR)"` and `--boot "$(BOOT)"` when they are given. It fails with a plain message when FILE is missing. Add a comment block in the style of the viewer targets and add `edf` to `.PHONY`.

7. Update the docs as in requirements 32 and 33.
   - specs/tech-stack.md: add export_edf.py, edfplus.py, and recording_text.py to the tools list, add a paragraph on the export with its command, venv, `make edf`, and the reader note of requirement 32, and add edfio 0.4.18 as a test-only package with its Apache 2.0 licence.
   - README.md: add a short "Export a recording as EDF+" section after "View a recording" with the command, the file naming, what the file holds, and the MNE note.

8. Run `ruff check tools/recording_text.py tools/edfplus.py tools/export_edf.py tools/compare_session.py tests/tools/test_export_edf.py`, `reference/.venv/bin/python -m pytest tests/tools -q`, `make python`, and `make check`, and fix the failures. ruff 0.15.18 is on the PATH from the user's own Python, and the repo has no ruff settings, so it runs with its defaults.

## Changes during implement

1. Check 1 case 19 found that read_gzip_text() lost up to 64 KiB of text before the cut, because gzip's read() gathers several steps and drops them all when the stream ends early. On the first half of record_log.txt.gz it gave 114597 lines where the stream holds 114841. That goes against requirement 9, so the moved reader now calls read1(), which gives one step at a time. This is the only change to the moved code. compare_session.py now reads a little more of a cut file, and its tests pass unchanged.
2. compare_session.py imports only read_recording() and record_patterns(), which are the names it uses, because ruff refuses imports that are not used. Its gzip and re imports went with the moved code. `cs.read_recording` still works.
3. Check 1 case 6 gave the record starts of command_log_505078862.edf as j and (946328952 - 234313) / 1e6 + (j - 945). That boot has a CLOCK line, so by requirement 25 the file starts at the whole second, and every record starts 0.243832 seconds later, as the case's own start time 06:01:06.243832 says. The test now checks that the first start is 0.243832 and that each start minus it equals the listed value. The code did not change.
4. EdfHeader holds the start date and time as a date and a time, or None when there is no clock. tools/edfplus.py writes the header fields from them with startdate_text(), starttime_text(), and plus_date_text(), so the 01.01.85 placeholder and the yy rule live with the other EDF+ rules. A start date before 1985 raises EdfError. The onset check is named check_record_onsets(). edfplus.py also holds the annotation signal's description as ANNOTATION_SIGNAL and checks the shape and range of the digital samples before it writes them.
5. annotations_for() takes the file's start on the timer, so it gives onsets from the file start, and it also gives the count of W lines not placed for each stretch, which the log names.
6. export_edf.py splits the plan's steps into a few more small functions, such as take_clock(), take_record(), window_t0s(), build_files(), and log_summary(). A gzip file whose data is damaged, which raises zlib.error, is reported as not a gzip file that can be read. With `--out-dir`, the folder is made when it does not exist, because `make edf OUT_DIR=...` in check 3 names a new folder.
7. specs/tech-stack.md also gains a line on edfio's licence in its Licences and credits section.
8. Check 5 was run as a sanity check on check5/table.txt.gz. It gave table_2565193163.edf, EDF+D, 177 records, a start of 2026-10-28 08:48:35.250172, which equals the CLOCK line's local time for R0, 168 answers, 7 face changes, and 3 stretch starts, and its digital samples equal the digital of replay's samples. The validate stage still records the result.
