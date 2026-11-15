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

## Set up and issue licenses from the web

For web-managed signing keys, mount a private persistent volume on the management
service. Set OMDA_SIGNING_KEY_DIR to the mount path and set
OMDA_SIGNING_STORAGE_PASSWORD to a strong random secret in the management service
variables. Back up the volume and preserve its password separately. Keep the path
and password stable across deployments. Use the same storage on every process that
issues licenses.

Sign in as a superuser. Under **Licenses → Signing Setup**, generate a default
signing key or import the existing encrypted Ed25519 PEM and its password. Keys
are encrypted at rest and the page exposes only the public key. A legacy key
configured with OMDA_ISSUER_PRIVATE_KEY and OMDA_ISSUER_KEY_PASSWORD continues to
serve as the default when a stored default is absent.

Create the hotel, then create its installation. A unique ID is prefilled for a
new setup. For an existing hotel, use its current OMDA_LICENSE_INSTALLATION.
Under **Installations → Actions → License Setup**, copy OMDA_LICENSE_PUBLIC_KEY
and OMDA_LICENSE_INSTALLATION into that hotel's backend variables. If the hotel
already uses a different signing key, import its existing encrypted PEM in
this dialog before issuing keys to it. A dedicated key takes precedence over
the default. Only create a different key for an existing installation when the
hotel is ready to switch its public key and activate a newly issued license.

Under **Licenses → Issue License Key**, select the hotel installation, choose a
plan, and confirm the dates and branch limit. Copy the issued key into the hotel
system's License settings. For renewal, issue and activate a new license using
the same installation and signing key.
