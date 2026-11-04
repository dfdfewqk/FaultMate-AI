# Paderborn K001 authenticity gate (read-only)

The K001 original source is a **single healthy bearing**, with recordings from four operating conditions (20 recordings each). Do not label any K001 recording as damaged.

Official dataset: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download
Archive index: https://groups.uni-paderborn.de/kat/BearingDataCenter/
Independent archived copy and K001 MD5: https://zenodo.org/records/15845309

Reference K001 MD5 from the Zenodo archived copy:
`af6dc58283d356cd438e7738a2d525b8` (listed size about 173.9 MB).

From a PowerShell terminal at the **Git-cloned FaultMate-AI root**, with 7-Zip installed:

```powershell
& '.\.venv-ml\Scripts\python.exe' scripts\verify_k001_archive.py --archive 'C:\Users\User\Downloads\FaultMateAI_REUPLOAD\FaultMate-AI-git\data\raw\K001.rar'
```

The tool uses only the Python standard library and 7-Zip. Any suitable Python 3.10+ interpreter is acceptable. It does not extract raw signals or edit data.

An exit status of 0 confirms agreement with the archived copy's MD5, archive integrity, and a consistent inventory of 80 recordings (4 conditions × 20). It **does not confirm signal calibration or units**. After successful source verification, run:

```powershell
& '.\.venv-ml\Scripts\python.exe' scripts\inspect_paderborn_archive.py --archive 'C:\Users\User\Downloads\FaultMateAI_REUPLOAD\FaultMate-AI-git\data\raw\K001.rar'
```

The inspector reports units as **unverified** until documentary sensor-calibration evidence is checked. Do not manufacture source units or bypass fail-closed behavior. No CSV training or model enablement until that evidence is reviewed.

A 13 MB archive with `K001_damaged_1.mat` is inconsistent with the official source and must not be treated as K001 training data, even if 7-Zip says it is internally intact.

Never commit downloaded RAR/MAT files, calibration secrets or models derived from unverified data. Dataset terms: CC BY-NC 4.0; noncommercial research use with attribution.
