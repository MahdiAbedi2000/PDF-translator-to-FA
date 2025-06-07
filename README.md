# مترجم هوشمند کتاب PDF (انگلیسی به فارسی)

این برنامه یک ابزار تحت وب برای ترجمه کتاب‌های PDF از زبان انگلیسی به فارسی با استفاده از هوش مصنوعی Gemini است.

## ویژگی‌ها

- ترجمه کتاب‌های PDF از انگلیسی به فارسی
- نمایش پیشرفت ترجمه به صورت زنده
- ترجمه به صورت بخش‌بندی شده (هر 5 صفحه)
- امکان دانلود ترجمه به صورت فایل PDF و متن
- رابط کاربری جذاب و واکنش‌گرا
- نمایش زمان تخمینی باقی‌مانده

## پیش‌نیازها

- Python 3.8 یا بالاتر
- کلید API Gemini
- poppler-utils (برای کار با فایل‌های PDF)

## نصب و راه‌اندازی

1. کلون کردن مخزن:
```bash
git clone https://github.com/yourusername/pdf-translator.git
cd pdf-translator
```

2. نصب وابستگی‌ها:
```bash
pip install -r requirements.txt
```

3. نصب poppler-utils (برای سیستم‌عامل‌های مختلف):

   - **ویندوز**: دانلود از [این لینک](https://github.com/oschwartz10612/poppler-windows/releases/) و اضافه کردن به PATH
   - **لینوکس**: `sudo apt-get install poppler-utils`
   - **مک**: `brew install poppler`

4. تنظیم کلید API:
   - فایل `.env` را ویرایش کنید و کلید API Gemini خود را در آن قرار دهید:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   برای گرفتن api رایگان جمنای به سایت https://aistudio.google.com/apikey وارد شوید و کلید رایگان بگیرید.

5. اجرای برنامه:
```bash
python app.py
```

6. مرورگر خود را باز کنید و به آدرس `http://localhost:5000` بروید.

## نحوه استفاده

1. فایل PDF خود را با کشیدن و رها کردن یا انتخاب از طریق دکمه آپلود کنید.
2. روی دکمه "شروع ترجمه" کلیک کنید.
3. پیشرفت ترجمه را مشاهده کنید و منتظر تکمیل آن بمانید.
4. پس از تکمیل، می‌توانید ترجمه را به صورت PDF یا متن دانلود کنید.

## ساختار پروژه

- `app.py`: فایل اصلی برنامه Flask
- `templates/`: قالب‌های HTML
- `static/`: فایل‌های استاتیک (CSS، JavaScript، فونت‌ها)
- `uploads/`: محل ذخیره فایل‌های آپلود شده
- `outputs/`: محل ذخیره فایل‌های ترجمه شده



## سپاسگزاری

- فونت وزیر از [Rastikerdar](https://github.com/rastikerdar/vazirmatn)
- API Gemini از Google
