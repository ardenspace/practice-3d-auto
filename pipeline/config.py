import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BLENDER_BIN = os.environ.get(
    "VW_BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender"
)
