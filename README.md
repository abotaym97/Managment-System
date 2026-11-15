# لوحة اشتراكات OMDA

مشروع مستقل. الواجهة العربية تعرض الفنادق وبيئاتها وسجل الاشتراكات. أضف السجلات من /admin/ بحساب مدير اللوحة. عدد الفروع وحالة التفعيل تُسجّلان يدويًا في هذه النسخة.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010
```

محليًا تستخدم SQLite. للإنتاج عيّن DJANGO_DEBUG=0 وDJANGO_SECRET_KEY وDJANGO_ALLOWED_HOSTS وDATABASE_URL لقاعدة PostgreSQL منفصلة. شغّل migrate وcollectstatic واضبط خادم الإنتاج لخدمة STATIC_ROOT.


## ربط الفندق بالمزامنة

أنشئ بيئة التشغيل بالمعرّف نفسه الموجود في إعدادات ترخيص الفندق.
من /admin/ افتح Installations، حدّد سجلًا واحدًا، واختر «إصدار أو استبدال رمز المزامنة». انسخ الرمز عند ظهوره.
في خدمة الباكند التي تشغّل عامل عمليات الفندق، اضبط OMDA_MANAGEMENT_URL بعنوان اللوحة الأساسي وOMDA_MANAGEMENT_TOKEN بالرمز. يمكن ضبط OMDA_RELEASE_VERSION لعرض الإصدار، وإلا يستخدم العامل معرّف كومت Railway عند توفره.
شغّل العامل أو أعد نشره. يرسل أول تقرير بعد أول دورة عمليات ثم كل عشر دقائق. في الإنتاج استخدم HTTPS. يظهر الملخص ووقت استلامه في تفاصيل الفندق.
يجب تطبيق ترحيل اللوحة 0002 قبل الربط. إصدار رمز بديل يلغي السابق.

## التشغيل على Railway

حدّد Start Command بالقيمة التالية، وأعد النشر بعد رفع ملفات المشروع إلى المستودع المرتبط.

```sh
python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

اضبط متغيرات الإنتاج المذكورة أعلاه. أضف دومين خدمة Railway إلى DJANGO_ALLOWED_HOSTS دون https://.
