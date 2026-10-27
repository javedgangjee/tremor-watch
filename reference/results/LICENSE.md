# Licence of the PADS results

The files in this folder and tests/pads/pads_match.md are made from the PADS dataset. They hold the toolbox's and the C detector's answers for each PADS recording window, and counts made from those answers. No PADS sensor readings are stored here.

PADS 1.0.0 is under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International licence (CC BY-NC-SA 4.0), https://creativecommons.org/licenses/by-nc-sa/4.0/. These files are under the same licence. They may not be used for commercial purposes, and a work made from them must carry the same licence.

## Changes from the dataset

reference/pads_counts.py and tests/pads/pads_match.py ran the ParaDigMa 1.1.2 tremor detector and the C detector on each recording's gyroscope readings. They kept one row per 4-second window with the subject number, the group, the task, the wrist, and the detector's answers, and they counted how often the detector fired in each task and group.

## Citation

Varghese, J., Brenner, A., Plagwitz, L., van Alen, C., Fujarski, M., & Warnecke, T. (2024). PADS - Parkinsons Disease Smartwatch dataset (version 1.0.0). PhysioNet. RRID:SCR_007345. https://doi.org/10.13026/m0w9-zx22

Varghese, J., Brenner, A., Fujarski, M., van Alen, C.M., Plagwitz, L., & Warnecke, T. (2024). Machine Learning in the Parkinson's disease smartwatch (PADS) dataset. npj Parkinsons Dis. 10, 9. https://doi.org/10.1038/s41531-023-00625-7

Pollard, T., Moody, B. E., Lehman, L., Gow, B., Fernandes, C., Xie, C., Johnson, A., Mark, R. G., & Heldt, T. (2026). PhysioNet as a global platform for biomedical research. Nature Health. https://doi.org/10.1038/s44360-026-00096-z
