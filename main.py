import csv
import io

import httpx
from fastapi import FastAPI, HTTPException, Query

BASE_URL = "https://data.go.th"
DATASET_ID = "zoo-visitors2569"
RESOURCE_ID = "0ecc96cf-d914-42a1-b184-dbbd013c3c9c"
FISCAL_YEAR = 2569
PUBLISHER = "องค์การสวนสัตว์แห่งประเทศไทย ในพระบรมราชูปถัมภ์"

app = FastAPI(
    title="Zoo Visitors API (ปีงบประมาณ 2569)",
    description="RESTful API ที่ดึงข้อมูลสถิติผู้เข้าชมสวนสัตว์จาก Data.go.th",
    version="1.0.0",
)


def fetch_from_datastore(limit: int) -> list[dict]:
    """วิธีที่ 1: เรียก CKAN Datastore API ของ data.go.th"""
    r = httpx.get(
        f"{BASE_URL}/api/3/action/datastore_search",
        params={"resource_id": RESOURCE_ID, "limit": limit},
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise ValueError("datastore_search ไม่สำเร็จ")
    return body["result"]["records"]


def fetch_from_csv(limit: int) -> list[dict]:
    """วิธีที่ 2 (สำรอง): หาลิงก์ไฟล์ของ resource แล้วอ่าน CSV"""
    r = httpx.get(
        f"{BASE_URL}/api/3/action/resource_show",
        params={"id": RESOURCE_ID},
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    file_url = r.json()["result"]["url"]
    f = httpx.get(file_url, timeout=30, follow_redirects=True)
    f.raise_for_status()
    text = f.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))[:limit]


@app.get("/")
def root():
    return {"message": "Zoo Visitors API", "docs": "/docs", "endpoint": "/api/zoo-visitors"}


@app.get("/api/zoo-visitors")
def zoo_visitors(limit: int = Query(100, ge=1, le=1000, description="จำนวนรายการสูงสุด")):
    method = "datastore_search"
    try:
        records = fetch_from_datastore(limit)
    except Exception:
        try:
            method = "csv_file"
            records = fetch_from_csv(limit)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"ดึงข้อมูลจาก Data.go.th ไม่สำเร็จ: {e}")

    return {
        "source": {
            "name": "Data.go.th (Open Government Data of Thailand)",
            "publisher": PUBLISHER,
            "dataset": DATASET_ID,
            "dataset_url": f"{BASE_URL}/dataset/{DATASET_ID}",
            "resource_id": RESOURCE_ID,
            "fetched_by": method,
        },
        "fiscal_year": FISCAL_YEAR,
        "count": len(records),
        "records": records,
    }
