import os,hmac,hashlib,json,logging,base64
from datetime import datetime,timezone
from typing import Any
from fastapi import FastAPI,HTTPException,Request,Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from pymongo import MongoClient,DESCENDING
from dotenv import load_dotenv
load_dotenv();logging.basicConfig(level=logging.INFO);log=logging.getLogger('inventory-api')
app=FastAPI(title='Inventory & Order Integration API',version='1.0.0');app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
client=None;db=None
try:
 client=MongoClient(os.getenv('MONGODB_URI','mongodb://localhost:27017'),serverSelectionTimeoutMS=1500);client.admin.command('ping');db=client[os.getenv('MONGODB_DATABASE','inventory_dashboard')];db.orders.create_index([('external_order_id',1),('source',1)],unique=True,sparse=True);db.orders.create_index([('updated_at',DESCENDING)]);db.products.create_index([('sku',1)],unique=True,sparse=True)
except Exception as e:log.warning('MongoDB unavailable at startup: %s',e)
class OrderIn(BaseModel):
 external_order_id:str=Field(min_length=1,max_length=100);source:str=Field(default='manual',max_length=30);customer:str=Field(default='Unknown customer',max_length=200);status:str=Field(default='pending',max_length=40);total:float=Field(ge=0);currency:str=Field(default='INR',max_length=3);items:list[dict[str,Any]]=Field(default_factory=list)
class StockUpdate(BaseModel):
 sku:str=Field(min_length=1,max_length=80);name:str=Field(min_length=1,max_length=200);quantity:int=Field(ge=0);reorder_level:int=Field(default=5,ge=0);warehouse:str=Field(default='Main warehouse',max_length=100)
def require_db():
 if db is None:raise HTTPException(503,'MongoDB is not connected. Configure MONGODB_URI and start MongoDB.')
 return db
def serialize(doc):
 if not doc:return doc
 doc=dict(doc);doc['id']=str(doc.pop('_id',''))
 for k in ('created_at','updated_at'):
  if isinstance(doc.get(k),datetime):doc[k]=doc[k].isoformat()
 return doc
@app.get('/health')
def health():return {'status':'ok','service':'inventory-order-integration-api','database':'connected' if db is not None else 'unavailable','timestamp':datetime.now(timezone.utc).isoformat()}
@app.get('/api/orders')
def list_orders(limit:int=100):return {'data':[serialize(d) for d in require_db().orders.find().sort('updated_at',DESCENDING).limit(max(1,min(limit,500)))]}
@app.post('/api/orders')
def create_order(payload:OrderIn):
 database=require_db();now=datetime.now(timezone.utc);doc=payload.model_dump();doc.update({'created_at':now,'updated_at':now,'sync_status':'synced','sync_attempts':0})
 try:
  r=database.orders.insert_one(doc);doc['_id']=r.inserted_id;log.info('order_created source=%s external_order_id=%s',payload.source,payload.external_order_id);return {'data':serialize(doc)}
 except Exception as e:
  if e.__class__.__name__=='DuplicateKeyError':return {'data':serialize(database.orders.find_one({'external_order_id':payload.external_order_id,'source':payload.source})),'duplicate':True}
  log.exception('order_create_failed');raise HTTPException(500,'Could not create order')
@app.get('/api/inventory')
def list_inventory():return {'data':[serialize(d) for d in require_db().products.find().sort('name',1).limit(500)]}
@app.put('/api/inventory')
def upsert_inventory(payload:StockUpdate):
 database=require_db();now=datetime.now(timezone.utc);database.products.update_one({'sku':payload.sku},{'$set':{**payload.model_dump(),'updated_at':now},'$setOnInsert':{'created_at':now}},upsert=True);return {'data':serialize(database.products.find_one({'sku':payload.sku}))}
@app.get('/api/metrics')
def metrics():
 orders=list(require_db().orders.find({}, {'total':1,'status':1,'sync_status':1}));return {'data':{'orders':len(orders),'revenue':round(sum(float(o.get('total',0)) for o in orders),2),'pending':sum(o.get('status') in ('pending','unfulfilled','processing') for o in orders),'syncErrors':sum(o.get('sync_status')=='error' for o in orders)}}
def verify_signature(raw,secret,provided,encoding='hex'):
 if not secret:return True
 if not provided:return False
 digest=hmac.new(secret.encode(),raw,hashlib.sha256).digest();expected=base64.b64encode(digest).decode() if encoding=='base64' else digest.hex();return hmac.compare_digest(expected,provided)
@app.post('/webhooks/shopify')
async def shopify_webhook(request:Request,x_shopify_hmac_sha256:str|None=Header(default=None)):
 raw=await request.body()
 if not verify_signature(raw,os.getenv('SHOPIFY_WEBHOOK_SECRET',''),x_shopify_hmac_sha256,'base64'):raise HTTPException(401,'Invalid Shopify webhook signature')
 try:
  b=json.loads(raw or b'{}');eid=str(b.get('id') or b.get('order_number') or '')
  if not eid:raise ValueError('missing order id')
  payload=OrderIn(external_order_id=eid,source='shopify',customer=b.get('email') or 'Shopify customer',status=str(b.get('fulfillment_status') or 'pending'),total=float(b.get('total_price') or 0),currency=b.get('currency') or 'INR',items=b.get('line_items') or []);return create_order(payload)
 except (ValueError,TypeError) as e:raise HTTPException(400,f'Invalid Shopify payload: {e}')
@app.post('/webhooks/razorpay')
async def razorpay_webhook(request:Request,x_razorpay_signature:str|None=Header(default=None)):
 raw=await request.body()
 if not verify_signature(raw,os.getenv('RAZORPAY_WEBHOOK_SECRET',''),x_razorpay_signature):raise HTTPException(401,'Invalid Razorpay webhook signature')
 try:
  b=json.loads(raw or b'{}');event=b.get('event','payment.updated');payment=b.get('payload',{}).get('payment',{}).get('entity',{});pid=str(payment.get('id') or '')
  if not pid:raise ValueError('missing payment id')
  require_db().payment_events.update_one({'payment_id':pid},{'$set':{'payment_id':pid,'event':event,'status':payment.get('status','unknown'),'amount_paise':payment.get('amount',0),'updated_at':datetime.now(timezone.utc)}},upsert=True);log.info('razorpay_event_received event=%s payment_id=%s',event,pid);return {'received':True,'event':event}
 except (ValueError,TypeError) as e:raise HTTPException(400,f'Invalid Razorpay payload: {e}')
@app.post('/api/sync/retry')
def retry_failed_syncs():
 result=require_db().orders.update_many({'sync_status':'error'},{'$set':{'sync_status':'queued','updated_at':datetime.now(timezone.utc)},'$inc':{'sync_attempts':1}});log.info('sync_retry_queued count=%s',result.modified_count);return {'queued':result.modified_count}
