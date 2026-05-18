import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# xAI
XAI_API_KEY: str = os.environ.get("XAI_API_KEY", "")
XAI_MODEL: str   = os.environ.get("XAI_MODEL", "")

# Output directory
OUTPUT_DIR: Path = Path(os.environ["YTLANG_OUTDIR"]).expanduser()

# Templates directory — default to ytlang/render/templates/
TEMPLATES_DIR: Path = Path(
    os.environ.get("YTLANG_TEMPLATES_DIR",
                   Path(__file__).parent / "render" / "templates")
)
