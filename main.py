import csv
import io
import json
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query

BASE_URL = "https://data.go.th"
DATASET_ID = "zoo-visitors2569"
RESOURCE_ID = "0ecc96cf-d914-42a1-b184-dbbd013c3c9c"
FISCAL_YEAR = 2569
PUBLISHER = "องค์การสวนสัตว์แห่งประเทศไทย ในพระบรมราชูปถัมภ์"
SNAPSHOT_FILE = Path(__file__).with_name("zoo_snapshot.json")

# บางเว็บ (รวมถึง data.go.th) บล็อกคำขอที่ไม่มี User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/csv, */*",
    "Accept-Language": "th,en;q=0.8",
}

app = FastAPI(
    title="Zoo Visitors API (ปีงบประมาณ 2569)",
    description="RESTful API ที่ดึงข้อมูลสถิติผู้เข้าชมสวนสัตว์จาก Data.go.th",
    version="1.1.0",
)


def fetch_from_datastore(limit: int) -> list[dict]:
    """วิธีที่ 1: เรียก CKAN Datastore API ของ data.go.th"""
    r = httpx.get(
        f"{BASE_URL}/api/3/action/datastore_search",
        params={"resource_id": RESOURCE_ID, "limit": limit},
        headers=HEADERS,
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise ValueError("datastore_search ไม่สำเร็จ")
    return body["result"]["records"]


def fetch_from_csv(limit: int) -> list[dict]:
    """วิธีที่ 2: หาลิงก์ไฟล์ของ resource แล้วอ่าน CSV"""
    r = httpx.get(
        f"{BASE_URL}/api/3/action/resource_show",
        params={"id": RESOURCE_ID},
        headers=HEADERS,
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    file_url = r.json()["result"]["url"]
    f = httpx.get(file_url, headers=HEADERS, timeout=30, follow_redirects=True)
    f.raise_for_status()
    text = f.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))[:limit]


def read_snapshot(limit: int) -> tuple[list[dict], str]:
    """วิธีที่ 3: อ่านสำเนาข้อมูลจริงที่บันทึกไว้จาก Data.go.th (ดู save_snapshot.py)"""
    data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return data["records"][:limit], data.get("fetched_at", "unknown")


@app.get("/")
def root():
    return {"message": "Zoo Visitors API", "docs": "/docs", "endpoint": "/api/zoo-visitors"}


@app.get("/api/zoo-visitors")
def zoo_visitors(limit: int = Query(100, ge=1, le=1000, description="จำนวนรายการสูงสุด")):
    errors = []
    method = "datastore_search"
    snapshot_at = None
    records = None

    try:
        records = fetch_from_datastore(limit)
    except Exception as e:
        errors.append(f"datastore_search: {e}")

    if records is None:
        try:
            method = "csv_file"
            records = fetch_from_csv(limit)
        except Exception as e:
            errors.append(f"csv_file: {e}")

    if records is None and SNAPSHOT_FILE.exists():
        try:
            method = "snapshot"
            records, snapshot_at = read_snapshot(limit)
        except Exception as e:
            errors.append(f"snapshot: {e}")

    if records is None:
        raise HTTPException(
            status_code=502,
            detail={"message": "ดึงข้อมูลจาก Data.go.th ไม่สำเร็จ", "errors": errors},
        )

    source = {
        "name": "Data.go.th (Open Government Data of Thailand)",
        "publisher": PUBLISHER,
        "dataset": DATASET_ID,
        "dataset_url": f"{BASE_URL}/dataset/{DATASET_ID}",
        "resource_id": RESOURCE_ID,
        "fetched_by": method,
    }
    if snapshot_at:
        source["snapshot_fetched_at"] = snapshot_at
        source["note"] = "สำเนาข้อมูลจริงที่ดึงจาก Data.go.th ตามเวลาที่ระบุ (ใช้เมื่อเรียกสดไม่ได้)"

    return {
        "source": source,
        "fiscal_year": FISCAL_YEAR,
        "count": len(records),
        "records": records,
    }