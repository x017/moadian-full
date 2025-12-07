# moadian-full

کتابخانه جامع پایتون برای اتصال به سامانه مودیان (سازمان امور مالیاتی ایران) - نسخه دوم با گواهی امضا.

این پکیج یک نسخه بهبود یافته (Fork) از کتابخانه moadian2 است که قابلیت‌های زیر به آن افزوده شده است:
* ساخت خودکار و استاندارد فاکتور (Invoice Builder)
* تولید خودکار شماره مالیاتی (Tax ID Generator) با الگوریتم صحیح
* مدیریت سریال‌های یکتا برای جلوگیری از خطای تکراری بودن (Serial Manager)
* محاسبه خودکار مبالغ (مالیات، جمع کل و ...)
* اصلاح الگوریتم Verhoeff برای محاسبه رقم کنترلی

## نصب

نصب با pip:

```bash
pip install moadian-full
```

نصب با uv:

```bash
uv add moadian-full
```

## شروع سریع

```python
from moadian_full import Moadian, InvoiceItem

# بارگذاری گواهی ها
with open("certs/private_key.pem", "rb") as f:
    private_key = f.read()
with open("certs/certificate.pem", "rb") as f:
    certificate = f.read()

# ایجاد کلاینت
# شناسه حافظه مالیاتی (6 کاراکتر) را وارد کنید
moadi = Moadian("ABCDEF", private_key, certificate)

# ساخت فاکتور با استفاده از بیلدر
# شناسه ملی فروشنده را وارد کنید
builder = moadi.create_invoice_builder("10101234567")

invoice = (builder
    .set_buyer("00123456789", buyer_type=2)  # خریدار حقیقی
    .add_item(InvoiceItem(
        sstid="2330001234567",   # شناسه کالا (13 رقم)
        sstt="عنوان کالا",       # شرح کالا
        fee=10000,               # قیمت واحد
        am=1,                    # تعداد
        vra=10                   # نرخ مالیات بر ارزش افزوده
    ))
    .build())

# ارسال فاکتور
result = moadi.send_invoice(invoice)
uid = result['result'][0]['uid']
print(f"UID: {uid}")

# بررسی وضعیت
status = moadi.check_status(uid)
print(f"Status: {status.get('status')}")
```

## راهنمای استفاده

### مقداردهی اولیه

برای شروع، نیاز به کلید خصوصی، گواهی امضا و شناسه حافظه مالیاتی دارید.

```python
from moadian_full import Moadian

moadi = Moadian(
    fiscal_id="ABCDEF",
    private_key=private_key_bytes,
    certificate=certificate_bytes,
    storage_path="./data"  # مسیر ذخیره فایل سریال ها (اختیاری)
)
```

### ساخت فاکتور با Invoice Builder

کلاس `InvoiceBuilder` پیچیدگی ساخت JSON استاندارد را از بین می‌برد و محاسبات ریاضی را به صورت خودکار انجام می‌دهد.

```python
from moadian_full import InvoiceItem
from datetime import datetime, timedelta

builder = moadi.create_invoice_builder("10101234567")

invoice = (builder
    # تنظیم اطلاعات خریدار
    .set_buyer(
        tin="00123456789",
        buyer_type=2  # 1: حقوقی, 2: حقیقی, 3: اتباع خارجی, 4: گذرنامه
    )
    
    # تنظیم نوع فاکتور (پیش فرض: فروش)
    .set_invoice_type(
        invoice_type=1,  # 1: فروش, 2: فروش نقدی
        pattern=1        # 1: فروش, 2: برگشت از فروش
    )
    
    # تنظیم نحوه پرداخت (پیش فرض: نقدی)
    .set_payment_method(1)  # 1: نقدی, 2: نسیه
    
    # افزودن اقلام فاکتور
    .add_item(InvoiceItem(
        sstid="2330001234567",
        sstt="نام کالا",
        fee=100000,
        am=2,
        vra=9,
        dis=0
    ))
    
    .build()
)
```

### کلاس InvoiceItem

این کلاس مسئولیت محاسبات هر ردیف کالا را بر عهده دارد. ورودی‌ها:

* `sstid`: شناسه کالا/خدمت (13 رقم)
* `sstt`: شرح کالا/خدمت
* `fee`: مبلغ واحد (ریال)
* `am`: تعداد/مقدار
* `mu`: واحد اندازه گیری (پیش‌فرض: 164 معادل عدد)
* `dis`: مبلغ تخفیف
* `vra`: نرخ مالیات بر ارزش افزوده (درصد)

### روش ارسال ساده (بدون Builder)

اگر نیاز به کنترل دقیق روی فرآیند ساخت ندارید، می‌توانید از متد ساده استفاده کنید:

```python
result = moadi.send_invoice_simple(
    seller_tin="10101234567",
    buyer_tin="00123456789",
    items=[
        {"sstid": "2330001234567", "sstt": "کالا 1", "fee": 10000, "am": 1, "vra": 10},
        {"sstid": "2330007654321", "sstt": "کالا 2", "fee": 20000, "am": 2, "vra": 10},
    ],
    buyer_type=2,
    payment_method=1
)
```

### استعلام وضعیت

استعلام وضعیت فاکتور با استفاده از UID:

```python
# استعلام تکی
status = moadi.check_status(uid, wait_seconds=5)

if status.get('status') == 'SUCCESS':
    print("فاکتور با موفقیت ثبت شد")
elif status.get('status') == 'FAILED':
    errors = status.get('data', {}).get('error', [])
    for err in errors:
        print(f"Error {err['code']}: {err['message']}")
```

سایر روش‌های استعلام:

```python
# استعلام با لیست UID
moadi.inquiry_by_uid(["uid1", "uid2"])

# استعلام با شماره مرجع
moadi.inquiry_by_reference_id(["ref1"])

# دریافت لیست فاکتورهای موفق
moadi.inquiry(status="SUCCESS", page_num=1, page_size=10)
```

### دریافت اطلاعات مودی و حافظه

```python
# دریافت اطلاعات حافظه مالیاتی
info = moadi.get_fiscal_information()

# دریافت اطلاعات مودی با کد ملی/اقتصادی
taxpayer = moadi.get_tax_payer("10101234567")
```

## مدیریت شماره مالیاتی و سریال

یکی از مشکلات رایج در سامانه مودیان، خطای تکراری بودن شماره مالیاتی یا سریال است. این کتابخانه به صورت خودکار این موضوع را مدیریت می‌کند.

### نحوه عملکرد مدیریت سریال
کلاس `SerialManager` آخرین سریال استفاده شده را در یک فایل JSON ذخیره می‌کند. هر بار که فاکتور جدیدی ساخته می‌شود، سریال به صورت خودکار افزایش می‌یابد.

اگر نیاز به تولید دستی شماره مالیاتی دارید:

```python
from moadian_full import TaxIdGenerator, SerialManager

# مدیریت سریال
manager = SerialManager("ABCDEF")
serial = manager.get_next()

# تولید شماره مالیاتی
generator = TaxIdGenerator("ABCDEF")
taxid = generator.generate(timestamp_ms, serial)
invoice_number = generator.get_invoice_number(serial)
```

## رفع خطاهای رایج

### خطای 0300101: مقدار فیلد شماره مالیاتی با اطلاعات سامانه منطبق نیست
این خطا معمولا به سه دلیل رخ می‌دهد:
1. سریال فاکتور تکراری است.
2. الگوریتم محاسبه رقم کنترلی (Verhoeff) اشتباه است.
3. تاریخ فاکتور در آینده است.

**راه حل:** از `InvoiceBuilder` استفاده کنید. این کلاس از `SerialManager` برای تضمین یکتایی سریال و از الگوریتم صحیح Verhoeff برای تولید Tax ID استفاده می‌کند.

### خطای 02041: خطای محاسباتی در مبلغ قبل از تخفیف
**راه حل:** از کلاس `InvoiceItem` استفاده کنید تا محاسبات ریاضی (ضرب تعداد در مبلغ واحد) به صورت خودکار و دقیق انجام شود.

### خطای 0100504: الگوی سریال رعایت نشده است
**راه حل:** شماره فاکتور (`inno`) باید دقیقا معادل هگزادسیمالِ سریالِ استفاده شده در `taxid` باشد و طول آن 10 کاراکتر باشد. کتابخانه این تبدیل را به صورت خودکار انجام می‌دهد.

## مقادیر ثابت (Constants)

### نوع فاکتور (inty)
* 1: فروش
* 2: فروش نقدی
* 3: صادرات
* 4: قرارداد

### الگوی فاکتور (inp)
* 1: فروش
* 2: برگشت از فروش
* 3: ابطال

### نوع خریدار (tob)
* 1: حقوقی
* 2: حقیقی
* 3: اتباع غیر ایرانی
* 4: گذرنامه
