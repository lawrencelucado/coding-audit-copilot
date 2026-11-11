"""Download and unzip the public ICD-10-CM code-descriptions zip into data/icd10/.

    python scripts/fetch_icd10.py <zip-url>

Get the URL for the fiscal year you want from
https://www.cms.gov/medicare/coding-billing/icd-10-codes
("Code Descriptions in Tabular Order"). ICD-10-CM is public domain.
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "data" / "icd10"


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://www.cms.gov/"):
        sys.exit("usage: python scripts/fetch_icd10.py https://www.cms.gov/files/zip/<file>.zip")
    with urllib.request.urlopen(sys.argv[1], timeout=120) as resp:
        payload = resp.read()
    DEST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for member in zf.namelist():
            name = Path(member).name
            if name.lower().startswith("icd10cm_order_") and name.lower().endswith(".txt"):
                (DEST / name).write_bytes(zf.read(member))
                print(f"saved {DEST / name}")
                return
    sys.exit("No icd10cm_order_*.txt file found in the zip.")


if __name__ == "__main__":
    main()
