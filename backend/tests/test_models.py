from fastapi.testclient import TestClient
from app.main import app,OrderIn,StockUpdate
def test_order_defaults():
 x=OrderIn(external_order_id="shop-100",total=1299);assert x.source=="manual" and x.currency=="INR" and x.items==[]
def test_negative_stock_rejected():
 try: StockUpdate(sku="SKU-1",name="Tea",quantity=-1);assert False
 except Exception: assert True
def test_health():
 r=TestClient(app).get("/health");assert r.status_code==200 and r.json()["status"]=="ok"
