# Tools

The top-level README covers `watch_cli.py` and `compare_session.py`. `gen_tables.py` and `gen_face_assets.py` make the detector tables and the face assets.

## Export a recording as EDF+

`tools/export_edf.py` writes a saved recording as EDF+ files that other biosignal programs can open. It reads saved files only and never opens the watch's port. Run it from the repo root after the C build.

```
reference/.venv/bin/python tools/export_edf.py session.txt.gz [--out-dir DIR] [--boot ID]
make edf FILE=session.txt.gz [OUT_DIR=DIR] [BOOT=ID]
```

It writes one file for each boot, named after the recording and the boot ID, so `session.txt.gz` with boot 2565193163 gives `session_2565193163.edf` beside the recording or in DIR. It never writes over a file. Each file holds the 100 Hz gyroscope samples that the detector used, in degrees per second, with each window's answer, each face change, each dose, and each stretch start as annotations. The boot's clock gives the start date and time, and a boot with no clock gets the EDF+ placeholders. A gap between stretches stays a gap, so such a file is discontinuous EDF+D.

EDFbrowser and edfio keep the gaps. MNE-Python 1.13.2 places the data records of an EDF+D file back to back, so its times after a gap are wrong, and it drops annotations past the end of the joined data. A boot with no gap gives a continuous EDF+C file, which every reader places correctly.
