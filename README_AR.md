# تاج تريدر OTC — Mobile Web App

نسخة أولية حقيقية لمسار:
الهاتف → سيرفر تاج تريدر → PyQuotex/WebSocket → شموع OTC → تحليل M1.

## مهم
- لا ينفذ صفقات ولا يحتوي buy().
- التحليل للقراءة فقط.
- ابدأ بحساب Quotex Demo.
- PyQuotex غير رسمي وقد يتوقف إذا تغيرت المنصة أو Cloudflare.
- لا تضع كلمة السر داخل index.html أو JavaScript.

## تشغيل السيرفر
1. Python 3.10+.
2. انسخ `.env.example` إلى `.env`.
3. ضع بيانات حساب Demo في `.env`.
4. `pip install -r requirements.txt`
5. `uvicorn app:app --host 0.0.0.0 --port 8000`
6. افتح `http://IP:8000` من الهاتف.

## الاستضافة
يمكن نشر المشروع على VPS يدعم Python واتصال WebSocket خارجي.
