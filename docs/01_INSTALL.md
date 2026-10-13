# Installation

## 1. Hardware & OS

- NVIDIA GPU with **CUDA 12.8+** (required for sm_120 / Blackwell, e.g. RTX 5060 Ti)
- Ubuntu 22.04 or 24.04 (other Linux distros should work; font paths may differ)
- ~16 GB VRAM minimum for Falcon-OCR + PP-DocLayoutV3

## 2. Python

Python 3.10 or 3.11. Create a fresh venv:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

## 3. PyTorch with CUDA 12.8

Install the build matching your CUDA version. For CUDA 12.8:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

Verify:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
```

## 4. Falcon-OCR dependencies

```bash
pip install -r requirements.txt
```

The first call to `generate_with_layout` will download the model weights
and build FlexAttention kernels via `torch.compile` — expect 2–5 minutes
on first run.

## 5. Arabic fonts (CRITICAL)

Only **Amiri** has been verified to produce searchable Arabic base letters.
Install:

```bash
sudo apt install fonts-hosny-amiri fonts-dejavu
```

Verify the paths in `config.py`:

```bash
ls -l /usr/share/fonts/truetype/amiri/Amiri-Regular.ttf
ls -l /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
```

If your distro places fonts elsewhere, update `ARABIC_FONT_PATH` and
`ENGLISH_FONT_PATH` in `config.py`.

## 6. Sanity check

```bash
python -c "from core.falcon_engine import FalconOCREngine; FalconOCREngine()"
```

You should see `Model loaded.` without errors.