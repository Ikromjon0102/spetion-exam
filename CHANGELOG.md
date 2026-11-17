# Changelog — Spetion Exam

Har bir versiyada nima qo'shilgani va tuzatilgani. Texnik tafsilotlar `CLAUDE.md` da.
Versiya raqamlari ish bosqichlariga qarab qo'yilgan (rasmiy release tag emas).

**Holat:** v1.0 jonli (https://exam.spetion.uz). v1.1 dan keyingilari lokal qurilgan va tekshirilgan; VPS'ga deploy qilinishi alohida qadam (backend `alembic upgrade head` + `pip install -r requirements.txt`, frontend `dist/`).

---

## v2.1 — O'zlashtirish dinamikasi (2026-noyabr)
- Har bir o'quvchi uchun bitta sahifa: yil boshidan hozirgacha barcha imtihonlar (nazorat, choraklik, har qanday fan). O'quvchi, ustoz va admin uchun bir xil.
- Umumiy daraja halqasi, "yil boshida → hozir" o'zgarishi, fanlar radari (animatsiya bilan), chorak-chorak ustunlari, vaqt chizig'i (sinf o'rtachasi bilan), fan × oy issiqlik xaritasi, fanlar bo'yicha kartalar.
- Sinfdagi o'rin **faqat ustoz/admin** ko'radi, o'quvchi ko'rmaydi.
- Ota-onalar uchun **A4 PDF hisobot** (logotip bilan, 2 sahifa, PDF kutubxonasiz).
- Qatnashmagan imtihon 0 deb hisoblanmaydi; tekshirilmagan yozma javob belgilanadi.
- Eski fanlar bo'yicha profil kartalari shu sahifa bilan almashtirildi.
- Tuzatish: telefonda ustoz sahifasida gorizontal siljish.
- Ma'lum kamchilik: tekshirilmagan yozma javob 0% sifatida chiziqqa ta'sir qiladi.

## v2.0 — Choraklik imtihonlar va tahlil (2026-noyabr)
- **Choraklik imtihon** (oliy ta'lim testi uslubida): 2 asosiy + 3 majburiy fan, masalan 189 ball, 180 daqiqa; 8-sinfdan yuqori sinflar; har bir blokni o'sha fan ustozi yozadi. Shablonlar, blok "tayyor" belgisi, admin nashr qiladi.
- Choraklik natijalar portfolioda "Choraklik" belgisi bilan; umumiy reytingda Hammasi / Nazorat / Choraklik filtri.
- Imtihon topshirish sahifasi qayta yozildi: kirish ekrani, savollar navigatori, bloklar, xavfsiz javob saqlash (qayta urinish), topshirishdan oldin tasdiq.
- **"O'quvchi ko'zi bilan ko'rish"** — imtihonni o'quvchi ekranida oldindan ko'rish.
- Savollar tahlili (qaysi savol qiyin, qaysi variant tanlangan), natijalarni CSV'ga eksport, chop etish.
- Imtihon ro'yxati endi **joriy chorak** bo'yicha (arxivlash o'rniga); chorak kalendari admin panelda tahrirlanadi (1-chorak 1.09–5.11, 2-chorak 6.11–11.01, 3-chorak 12.01–7.04, 4-chorak 8.04–1.07).
- **Parser qayta ishlandi** (3 ta haqiqiy fayl bilan): 15/14/0 → 20/20/20 savol. Bir qatorda bir nechta variant, qalin harf bilan belgilangan javob, jadval, pastki/yuqori indekslar, PDF darajalari.
- Yuklash endi saytni qotirmaydi (fon vazifasi).
- AI baholay olmagan yozma javob "ustoz tekshiradi" holatida (0 emas).
- O'zgarish: bitta qalin variant endi "ishonchli" (yuqori) deb hisoblanadi.

## v1.2 — Muallifga qulaylik, tezlik, boy matn (2026-oktyabr)
- Xatolar va tasdiqlar ekranda ko'rinadigan toast bilan (oldin sahifa tepasida yo'qolib qolardi).
- Parser: `20.Savol`, `A.Insert` kabi bo'shliqsiz belgilar; Word avto-raqamlash; kutilgan savollar soni ogohlantirishi.
- Tezlik: N+1 so'rovlar tuzatildi, dashboard bitta so'rov, route bo'yicha lazy yuklash, shriftlar o'zimizda.
- Qidiruv ko'rinishi (SEO): meta, sitemap, robots, manifest; chop etiladigan parol varaqlarida QR.
- **Boy matn va formulalar** (TipTap + KaTeX) savol/variantlarda, sanitizatsiya bilan.
- **Imtihon himoyasi** (maktab kompyuterlari): to'liq ekran, chiqib ketsa ogohlantirish, nusxalashni bloklash.
- **Arxiv** (bayroq sifatida), filtrlanadigan va sahifalanadigan imtihon ro'yxati, kunlar bo'yicha guruhlash.
- `Exam.status` hech qachon "active" bo'lmasligi sababli yolg'on belgilar tuzatildi — endi hisoblanadigan `phase` (draft/upcoming/live/finished).

## v1.1 — Birinchi demodan keyingi ishlar (2026-sentyabr–oktyabr)
- **Portfolio**: har fan bo'yicha chiziqli grafik (o'quvchi va ustoz uchun).
- **Sinf kunlik natijalari**: bitta jadval, rasm sifatida yuklab olib Telegramda ulashish (bot emas).
- **Umumiy reyting**: sinf, parallel sinflar (sinf darajasi) va maktab bo'yicha.
- **Past/yuqori o'zlashtiruvchilarni ko'rish** va natijalar sahifasini chop etish.
- **Imtihonni parallel sinflarga nusxalash**.
- **AI baholaydigan qisqa javob** (Haiku 4.5), ustoz o'zgartira oladi; ustoz etalon javob beradi.
- **Skrinshot qo'yish** (Ctrl+V) savol va variantlarga; variantlar soni 2 dan boshlab.
- Skanerlangan PDF/matematika testlari bilan ishlash: ikkita haqiqiy parser xatosi topilib tuzatildi, OCR cheklovi qabul qilindi.
- Qo'lda imtihon kiritish rejimi (faylsiz).
- Javob matni natijada imtihon oynasi yopilgandan keyin ochiladi (o'quvchilar bir-biriga aytib bermasligi uchun).
- Admin: to'liq tahrirlash/o'chirish (sinf, fan, o'quvchi, ustoz), sinf rahbari, ommaviy o'quvchi import, sinf bo'yicha parol almashtirish, parolni ko'rsatish tugmasi.
- Dashboard "Hozir jonli" bloki; chap yon panel; sinflar/ustozlar qidiruvi; keng ekran.
- Tuzatishlar: qorong'i rejimda belgilangan javob o'qilmasligi, natija sahifasidagi noto'g'ri savol tartibi, tugma ichida tugma, qora-qora raqamlar.
- Tahrirlash: imtihonni hech kim boshlamaguncha nashrdan keyin ham tahrirlash mumkin.

## v1.0 — Birinchi ishga tushirish
- O'quvchi sinfini tanlab kiradi, jadval bo'yicha imtihon topshiradi; server vaqt nazorati (`deadline_at`), avtomatik topshirish.
- Ustoz PDF/DOCX yuklaydi → parser savollarga ajratadi → ustoz tekshiradi → jadval qo'yib nashr qiladi.
- Avtomatik baholash, sinf bo'yicha reyting, fan bo'yicha statistika.
- UZ/RU interfeys, yorug/qorong'i rejim, parolni o'zgartirish.
- FastAPI + PostgreSQL + React (Vite/TypeScript); DigitalOcean VPS'da deploy: https://exam.spetion.uz.
- Maktab strukturasi (25 sinf, 20 fan, 48 ustoz) import qilingan.

---

## Keyingi rejalar (hal qilinmagan)
- Mavzu bo'yicha tahlil (savollarga mavzu belgisi kerak).
- Chorak ballini oldindan taxmin qilish.
- Natija sahifasida rasmli savollarni ko'rsatish.
- Sinf reytingida sinfdoshlar ismini yashirish (maktab qarori).
- Telefondan imtihon boshlashni taqiqlash (qaror qilinmagan).
