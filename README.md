# Spetion Exam Platform

O'quvchilar sinf tanlab login/parol bilan kiradi, o'qituvchilar PDF/DOCX
imtihon yuklaydi (avtomatik parse qilinadi), belgilangan vaqt oynasida
imtihon topshiriladi, natija avtomatik baholanadi va sinf bo'yicha reyting
chiqadi.

To'liq texnik spec: [`docs/spec.md`](docs/spec.md). Loyiha konteksti va
keyingi qadamlar: [`CLAUDE.md`](CLAUDE.md) — Claude Code bu papkani ochganda
shuni avtomatik o'qiydi.

## Birinchi marta ishga tushirish

### 1. Infra (Postgres, Redis, MinIO)

```bash
docker-compose up -d
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
copy .env.example .env       # Windows: copy, macOS/Linux: cp
# .env ichida JWT_SECRET ni o'zgartiring

uvicorn app.main:app --reload
```

API: http://localhost:8000/docs (Swagger — avtomatik generatsiya qilinadi)

Barcha endpointlar (auth — login + parol almashtirish, admin — tashkilot/
imtihon boshqaruvi, admin_management — sinf/fan/o'quvchi/o'qituvchi
qo'shish-tahrirlash, student, results) implement qilingan. Ma'lumotlar
bazasi jadvallarini yaratish Alembic orqali:

```bash
alembic upgrade head
```

Testlarni ishga tushirish (in-memory SQLite'da, Postgres shart emas):

```bash
pytest app/tests -q
```

120 test o'tadi (auth, parol almashtirish, admin boshqaruv (jumladan
ro'yxatdan ko'p o'quvchi qo'shish, sinf bo'yicha parolni almashtirish, sinf
rahbari huquqlari, fan o'qituvchisi uchun ko'rish huquqi va har bir bo'lim
uchun tahrirlash/o'chirish), nashr etilgan imtihonni qayta tahrirlash,
parser ishonch darajasining (`parse_confidence`) savolga saqlanishi,
savol/variantga rasm (skrinshot) biriktirish, publish validatsiyasi,
taymer/deadline, baholash, imtihon reytingi, sinf/parallel sinflar/maktab
bo'yicha umumiy reyting, o'quvchining fanlar bo'yicha o'zlashtirish
ko'rsatkichi, kunlik natijalarni sinf bo'yicha yig'ish (Telegram uchun
rasm eksporti), AI baholaydigan qisqa javob (short-answer) savollar —
publish validatsiyasi, AI baholash (Anthropic API bilan haqiqiy chaqiruv
mock qilinib sinovdan o'tkazilgan), ustoz tomonidan qayta baholash —,
imtihonni parallel sinflarga nusxalash,
DOCX/PDF parserlar — PDF parser ham sinov faylida, ham
OCR-fallback yo'lida, ham haqiqiy o'qituvchi fayllarida
tekshirilgan).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 — o'quvchi va o'qituvchi/admin oqimlari ishlaydi
(login, imtihon topshirish, ko'rib chiqish/nashr qilish, reyting, parolni
almashtirish `/change-password`).

O'qituvchi/admin login qilgach chap tomonda **yig'iladigan/yoziladigan
yon menyu** (sidebar) ochiladi — Bosh sahifa, Imtihonlar, Sinflar va
(faqat admin uchun) Fanlar/O'quvchilar/O'qituvchilar, har biri alohida
menyu bandi sifatida (avvalgi tepadagi tab-bar o'rniga). Login qilgach
to'g'ridan-to'g'ri **Dashboard** sahifasiga (`/admin/dashboard`) tushiladi
— admin uchun sinflar/fanlar/o'quvchilar/o'qituvchilar soni + ikkita
diagramma (imtihonlar holati bo'yicha donut-chart, sinflar bo'yicha
o'quvchilar soni bar-chart), o'qituvchi uchun o'zining sinf-fan va
imtihonlari. Har ikkalasi ham e'tibor talab qiladigan (tekshirilmagan
savolli) va faol/yaqin imtihonlar ro'yxatini ko'radi.

**Sinflar** (`/classes`) — sinfni bosib uning batafsil sahifasiga
(`/classes/:id`) o'tiladi: fan bo'yicha qaysi o'qituvchi dars berishi,
o'quvchilar soni va **sinf rahbari** (admin tayinlaydi, dropdown orqali).
Sinf rahbariga biriktirilgan o'qituvchi o'z sinfining o'quvchilar
ro'yxatini to'liq boshqara oladi — qo'shish, **"Ro'yxatdan ko'p o'quvchi
qo'shish"** (Excel'dan nusxa ko'chirib, har qatorda bitta F.I.Sh. —
login/parol avtomatik yaratiladi), va **"Sinf bo'yicha parolni
almashtirish"** (butun sinfga bitta yangi parol, masalan `huquq2026`, ikki
bosqichli tasdiqlash bilan). Sinf rahbari bo'lmagan, lekin o'sha sinfda
dars beradigan fan o'qituvchisi ham o'quvchilar ro'yxatini (ism va login)
**ko'ra oladi** — faqat o'zgartira olmaydi (qo'shish/tahrirlash/o'chirish
tugmalari ko'rinmaydi, faqat sinf rahbari yoki admin uchun). Admin har
doim to'liq huquqqa ega. O'quvchi profilida (`/student/profile`) endi
har bir fan bo'yicha natijalar chizig'i (sparkline) chizib beriladi.

**Reyting** (`/ranking`, chap menyuda) — sinf ichida, **parallel sinflar
bo'yicha** (masalan barcha 7-sinflar — 7B va 7R — birgalikda, "7-sinflarda
kim eng zo'r" savoliga javob berish uchun) yoki butun maktab bo'yicha
o'quvchilarni **barcha imtihonlar o'rtacha foizi** bo'yicha saralab
ko'rsatadi (bitta imtihon uchun reyting sahifasi — `Sinf reytingi` —
avvalgidek alohida qoladi). Sinf bo'yicha ko'rish o'sha sinfga aloqasi bor
har qanday o'qituvchiga ochiq, parallel sinflar va maktab bo'yicha umumiy
reyting esa faqat admin uchun (boshqa sinf/o'qituvchilarning ma'lumotini
oshkor qilmaslik uchun).

**O'quvchi natijalari** — o'quvchilar ro'yxatida (O'quvchilar sahifasi va
sinf tafsilotlari) har bir o'quvchi qatorida **"Natijalar"** tugmasi bor —
bosilganda o'sha o'quvchining har bir fan bo'yicha o'rtacha foizi va
tendensiyasi (o'sish/pasayish/barqaror) ko'rsatiladi, eng past natijali
fan birinchi bo'lib chiqadi va rang bilan ajratiladi (qizil — past, sariq
— o'rtacha, yashil — yaxshi) — "Alijon qaysi fandan orqada qolyapti"
degan savolga tezda javob berish uchun.

**Nashr etilgan imtihonni qayta tahrirlash** — imtihon "Rejalashtirilgan"
yoki "Faol" holatga o'tgandan keyin ham, **hech qaysi o'quvchi hali
boshlamagan** bo'lsa, savollarni, javob variantlarini va jadvalni
(davomiylik/boshlanish/tugash) qayta tahrirlash mumkin. Birinchi o'quvchi
imtihonni boshlashi bilan u butunlay qulflanadi — bu qat'iy chegara, chunki
boshlangan urinish savollar tartibini va keyinchalik bahoni saqlab qoladi;
uni orqasidan o'zgartirish adolatni buzadi.

Savollarni tekshirish sahifasida (review) endi parser o'zi "ishonchim
komil emas" deb belgilagan savollar qizil belgi bilan alohida
ajratiladi ("Tekshirilmagan" belgisidan mustaqil — bittasi "hali
ko'rilmagan", ikkinchisi "parser o'zi noaniq o'qigan" degani), shunda
o'qituvchi qaysi savolga ko'proq e'tibor berish kerakligini bilib oladi.

**Savol/variantga rasm biriktirish** — murakkab formula yoki belgilarni
qayta yozib o'tirish shart emas: kompyuterning skrinshot vositasi bilan
kesib olingan rasm avtomatik almashinuv buferiga (clipboard) tushadi,
savol matni yoki variant maydoniga sichqoncha bilan bosib **Ctrl+V**
bosish kifoya — matn o'rniga aynan o'sha rasm ko'rsatiladi (parser
noto'g'ri o'qigan savolni tuzatishda ham, yangi savol qo'shishda ham
ishlaydi). "Matnga qaytarish" tugmasi bilan istalgan payt yana matn
kiritish rejimiga qaytish mumkin.

**Har qanday miqdordagi variant** — yangi savol qo'shishda endi aynan 4 ta
variant shart emas: "Variant qo'shish" va har bir qator yonidagi
"O'chirish" tugmalari bilan 2 tadan (masalan To'g'ri/Noto'g'ri) 8 tagacha
variant qo'yish mumkin — faqat aynan bitta to'g'ri javob belgilanishi
shart.

**Tahrirlash va o'chirish** — endi har bir bo'limda (Sinflar, Fanlar,
O'quvchilar, O'qituvchilar) "Tahrirlash" va "O'chirish" tugmalari bor.
O'chirish ikki bosqichli tasdiqlash bilan ishlaydi (birinchi bosishda
tugma qizil rangga o'tib "Ha, o'chirish" deb so'raydi, 4 soniya ichida
bosilmasa bekor bo'ladi). Agar o'chirilayotgan yozuv bilan bog'liq
haqiqiy ma'lumot bo'lsa (masalan sinfda o'quvchilar bor, o'quvchining
imtihon natijalari mavjud, o'qituvchi imtihon yaratgan), tizim buni rad
etib tushuntirish beradi — o'quvchi/o'qituvchi bilan bog'liq, lekin
zararsiz biriktirishlar (masalan sinf-fan biriktirmalari) esa avtomatik
tozalanadi.

Frontend `npm install` + `npm run build` (`tsc -b` + `vite build`) orqali
xatosiz build qilinganligi va butun oqim (login → imtihon topshirish →
taymer → baholash → reyting, ham o'quvchi, ham admin tomonidan) brauzerda
haqiqiy ishlab turgan serverga qarshi qo'lda tekshirilgan.

### 4. Celery (fon vazifalar — parsing, taymer sweep)

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info
```

### 5. Real maktab ma'lumotlarini import qilish (ixtiyoriy)

`backend/seed_data/spetion_school_data.json` — Spetion School'ning haftalik
dars jadvali (sinflar, fanlar, o'qituvchilar, kim qaysi sinfga qaysi fandan
dars beradi). Buni sinflar/fanlar/o'qituvchilar/`teacher_class_subjects`
jadvallariga import qilish uchun:

```bash
cd backend
python -m scripts.seed_school_data
```

Qayta ishga tushirish xavfsiz (idempotent — nom bo'yicha moslashtiradi,
dublikat yaratmaydi). Yangi yaratilgan barcha o'qituvchi hisoblari uchun
bitta vaqtinchalik parol beriladi (skript chiqishida ko'rsatiladi) — buni
haqiqiy foydalanishdan oldin albatta almashtiring.

## Loyiha strukturasi

```
backend/app/
  models/     — SQLAlchemy jadvallar
  routers/    — HTTP endpointlar (auth, student, admin_exams,
                admin_management, results)
  services/   — biznes mantiq (exam_service, attempt_service,
                grading_service, ranking_service, parsing_service)
  parsers/    — PDF/DOCX -> savollar (docx_parser, pdf_parser, text_split)
  tasks/      — Celery: parsing_tasks, exam_lifecycle_tasks
  tests/      — pytest (auth, publish, timer/deadline, grading, ranking, parser)
  scripts/    — seed_school_data.py (real dars jadvalini import qilish)
  seed_data/  — spetion_school_data.json (haftalik dars jadvali)
migrations/   — Alembic
frontend/src/
  api/        — backend bilan aloqa (authApi, studentApi, adminApi)
  auth/       — AuthContext, RequireRole
  components/ui/ — dizayn tizimi: Button, Badge, Card, ListRow,
                AnswerOption, AppHeader (o'quvchi uchun), AdminLayout
                (o'qituvchi/admin uchun chap sidebar), Logo, Icon,
                StatCard, Sparkline, BarChart, DonutChart, ConfirmButton
                (ikki bosqichli o'chirish tasdiqlash)
  styles/     — tokens.css (ranglar/tipografiya/spacing), global.css
  assets/logos/ — Spetion logotiplari (brend fayllaridan, o'zgartirilmagan)
  features/   — sahifalar (student/, admin/)
  hooks/      — useExamTimer
  utils/      — formatDate (o'zbekcha sana formatlash)
```

## Dizayn tizimi

Ranglar, tipografiya (Inter + Space Mono) va komponent patternlari
Spetion'ning real ishlab chiqilgan dizayn tizimidan olingan (mavjud
`dars_jadvali.html` ilovasidan tasdiqlangan qiymatlar). Asosiy qoidalar:
brend qizil rangi (`--brand-600`) faqat asosiy amal va faol holatlar uchun;
sahifa foni iliq oq-sarg'ish (`--surface`), kartalar esa sof oq
(`--surface-raised`) — soyasiz, faqat border bilan "ko'tarilgan" taassurot
beradi; ro'yxat qatorlari to'rtta holatga ega: oddiy, "hozir" (yashil),
"keyingi" (qizil border), "bo'sh" (chiziqli). Barcha tokenlar
`frontend/src/styles/tokens.css`da, both light va dark tema uchun.

## Tema (light/dark) va til (UZ/RU)

Interfeys (tugmalar, sarlavhalar, holat belgilari) UZ/RU o'rtasida
almashtiriladi — header'dagi **UZ | RU** tugmasi orqali (tanlov
`localStorage`da saqlanadi). Bu faqat interfeys uchun: imtihon
savollari/javoblari qaysi tilda yuklangan bo'lsa, shu tilda qoladi —
o'qituvchi test faylini qaysi tilda tayyorlagan bo'lsa, o'sha til bilan
yuboradi. Tema tugmasi (quyosh/oy) light/dark o'rtasida almashtiradi,
tanlov ham saqlanadi. Kod: `frontend/src/i18n/` va
`frontend/src/theme/`.

## Muhit haqida eslatma

Node.js va Docker Desktop shu sessiyada avtomatik o'rnatildi (winget
orqali). Docker'ning WSL2 backend'i esa **Administrator huquqi** talab
qiladi va buni Claude Code'ning o'zi bajara olmaydi — birinchi marta
ishlatishdan oldin:

```powershell
wsl --install
```

buyrug'ini "Run as Administrator" qilib ochilgan PowerShell'da bering,
so'ng kompyuterni qayta ishga tushiring. Shundan keyin
`docker-compose up -d` ishlaydi.

Shu vaqtgacha Docker/MinIO/Redis'siz ishlash uchun `backend/.env`da:
```
STORAGE_BACKEND=local
LOCAL_STORAGE_DIR=./local_storage
CELERY_EAGER=true
```
— fayllar diskka saqlanadi, parsing so'rov ichida sinxron bajariladi.
Docker to'liq ishga tushgach, bu ikki qatorni o'chirib tashlang (yoki
`.env`ni butunlay `.env.example`dan qayta yarating) — production'da
har doim MinIO + Celery worker ishlatiladi.

## Hali qilinmagan / keyingi qadamlar

- Migratsiya haqiqiy Postgres'ga qarshi hali ishga tushirilmagan —
  bu endi DigitalOcean VPS'da amalga oshiriladi (lokal Docker/WSL2 emas);
  sqlite'da strukturaviy va funksional to'liq tekshirilgan, VPS tayyor
  bo'lgach `alembic upgrade head`ni o'sha yerga qarshi ishga tushirish
  kifoya.
- PDF parser sintetik (reportlab bilan generatsiya qilingan) fayllarda va
  OCR-fallback yo'lida sinovdan o'tkazilgan, lekin haqiqiy skanerlangan/
  suratga olingan imtihon PDF faylida va murakkab matematik testlarda
  (formulalar, kasrlar) hali tekshirilmagan — haqiqiy fayllar bilan
  sinovdan o'tkazish rejalashtirilgan.

## Windows'da eslatma: `uvicorn --reload`

Bu muhitda `--reload` bir nechta fayl ketma-ket o'zgartirilganda ba'zan
keyingi o'zgarishlarni ko'rmay qoladi (404/422 xatolar eski kod asosida).
Agar backend xatti-harakati kodga mos kelmasa, avval serverni to'liq
to'xtatib (`taskkill //F //PID <pid>`), `--reload`siz qayta ishga
tushiring: `uvicorn app.main:app --port 8000`.
