import os, time, math, asyncio
from typing import List, Dict, Any
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from quotexapi.stable_api import Quotex

load_dotenv()
app = FastAPI(title="TAJ TRADER OTC", version="0.1")

EMAIL=os.getenv("QUOTEX_EMAIL","").strip()
PASSWORD=os.getenv("QUOTEX_PASSWORD","").strip()
EMAIL_PASS=os.getenv("QUOTEX_EMAIL_PASS","").strip() or None

client = Quotex(email=EMAIL, password=PASSWORD, email_pass=EMAIL_PASS)
lock = asyncio.Lock()

def num(v, default=None):
    try: return float(v)
    except: return default

def normalize(raw: Any) -> List[Dict[str,float]]:
    data = raw.get("data", raw) if isinstance(raw, dict) else raw
    if isinstance(data, dict):
        data = list(data.values())
    out=[]
    for c in data or []:
        if not isinstance(c, dict): continue
        o=num(c.get("open", c.get("openPrice")))
        h=num(c.get("high", c.get("max")))
        l=num(c.get("low", c.get("min")))
        cl=num(c.get("close", c.get("closePrice")))
        t=num(c.get("time", c.get("timestamp", c.get("from"))), 0)
        # بعض تدفقات Quotex قد ترسل price بدلاً من OHLC.
        p=num(c.get("price"))
        if cl is None and p is not None: o=h=l=cl=p
        if None not in (o,h,l,cl):
            out.append({"time":t,"open":o,"high":h,"low":l,"close":cl})
    out.sort(key=lambda x:x["time"])
    return out

def sma(values, n=50):
    if len(values)<n: return None
    return float(np.mean(values[-n:]))

def rsi(values, n=14):
    if len(values)<n+1: return None
    d=np.diff(np.array(values[-(n+1):], dtype=float))
    gains=np.where(d>0,d,0.0); losses=np.where(d<0,-d,0.0)
    ag=float(np.mean(gains)); al=float(np.mean(losses))
    if al==0: return 100.0
    rs=ag/al
    return 100-(100/(1+rs))

def analyze(candles):
    if len(candles)<55:
        return {"signal":"NO TRADE","reason":"شموع غير كافية","confidence":0}
    closes=[c["close"] for c in candles]
    ma50=sma(closes,50); rv=rsi(closes,14)
    last=candles[-1]; prev=candles[-2]
    recent=closes[-10:]
    slope=(recent[-1]-recent[0])/(abs(recent[0]) or 1)
    bull=bear=0; reasons=[]

    if last["close"]>ma50: bull+=1; reasons.append("فوق MA50")
    else: bear+=1; reasons.append("تحت MA50")

    if rv is not None:
        if rv<=35: bull+=1; reasons.append("RSI منخفض")
        elif rv>=65: bear+=1; reasons.append("RSI مرتفع")
        elif rv>52: bull+=1
        elif rv<48: bear+=1

    if slope>0.00025: bull+=1; reasons.append("مومنتم صاعد")
    elif slope<-0.00025: bear+=1; reasons.append("مومنتم هابط")

    body=last["close"]-last["open"]
    if body>0 and last["close"]>prev["high"]: bull+=1; reasons.append("كسر صاعد")
    elif body<0 and last["close"]<prev["low"]: bear+=1; reasons.append("كسر هابط")

    highs=[c["high"] for c in candles[-20:-1]]
    lows=[c["low"] for c in candles[-20:-1]]
    if last["close"]>max(highs): bull+=1; reasons.append("اختراق قمة 20 شمعة")
    if last["close"]<min(lows): bear+=1; reasons.append("كسر قاع 20 شمعة")

    # فلتر يمنع الإشارة عند تقارب الدرجات.
    best=max(bull,bear); diff=abs(bull-bear)
    if best<3 or diff<2:
        sig="NO TRADE"
    else:
        sig="CALL" if bull>bear else "PUT"
    confidence=min(95, int(45 + best*9 + diff*4)) if sig!="NO TRADE" else min(55,int(best*10))
    return {
        "signal":sig,"confidence":confidence,"bull":bull,"bear":bear,
        "rsi":round(rv,2) if rv is not None else None,
        "ma50":ma50,"last":last["close"],"reasons":reasons
    }

async def ensure_connected():
    if not EMAIL or not PASSWORD:
        raise HTTPException(503, "بيانات حساب Demo غير مضبوطة على السيرفر")
    if client.check_connect():
        return
    ok, reason = await client.connect()
    if not ok:
        raise HTTPException(503, f"فشل اتصال Quotex: {reason}")

@app.get("/api/health")
async def health():
    return {"ok":True,"configured":bool(EMAIL and PASSWORD),"connected":bool(client.check_connect())}

@app.get("/api/analyze")
async def analyze_asset(asset: str = Query(..., min_length=6)):
    asset=asset.strip().replace("-OTC","_otc").replace("-otc","_otc")
    async with lock:
        await ensure_connected()
        try:
            name, meta = await client.get_available_asset(asset, force_open=True)
            if not meta or not meta[2]:
                return {"asset":asset,"signal":"CLOSED","confidence":0,"reason":"الأصل مغلق حاليًا"}
            raw = await client.get_candles(asset, time.time(), 7200, 60)
            candles=normalize(raw)
            result=analyze(candles)
            result.update({"asset":asset,"candles":len(candles),"server_time":int(time.time())})
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"خطأ قراءة {asset}: {type(e).__name__}: {e}")

@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
