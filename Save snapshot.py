"""รันในเครื่องตัวเอง (ที่เรียก data.go.th ได้) เพื่อบันทึกข้อมูลจริงเป็นไฟล์ zoo_snapshot.json

วิธีรัน:  python save_snapshot.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

RESOURCE_ID = "0ecc96cf-d914-42a1-b184-dbbd013c3c9c"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}

r = httpx.get(
    "https://data.go.th/api/3/action/datastore_search",
    params={"resource_id": RESOURCE_ID, "limit": 1000},
    headers=HEADERS,
    timeout=30,
    follow_redirects=True,
)
r.raise_for_status()
body = r.json()
assert body.get("success"), "API ตอบว่าไม่สำเร็จ"

out = {
    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "resource_id": RESOURCE_ID,
    "records": body["result"]["records"],
}
Path(__file__).with_name("zoo_snapshot.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"บันทึกแล้ว {len(out['records'])} รายการ -> zoo_snapshot.json")