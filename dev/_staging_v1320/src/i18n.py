# -*- coding: utf-8 -*-
"""多语言（i18n）（v1.32.0，反馈 3）
=================================
用户原话：「个性化 设置 外观 中 加入 19种多语言支持，（英语、简体中文（基准语言）、
西班牙语、印地语、阿拉伯语、葡萄牙语、俄语、日语、德语、法语、韩语、意大利语、
土耳其语、荷兰）」。

设计取向 —— 为什么是「词典 + 回退」而不是 `QTranslator` / `tr()`
-----------------------------------------------------------------
`QTranslator` 依赖 `.ts` → `.qm` 的编译流程与 Linguist 工具链，而本软件是
**PyInstaller 单文件 exe**：多一个二进制资源就要多一条 `--add-data` 与一套构建期
依赖。更关键的是，本项目 1900+ 条中文字面量里绝大多数是**业务文案**
（刮削源说明、算法免责声明、真机调试结论），把它们全部翻译成 19 种语言既不现实、
也没有必要。

所以这里的口径是：**翻译「会改变用户操作路径的部分」，业务细节保持原文**。
具体覆盖：

1. **导航与页面名**（`NAV_KEYS` / `TOOL_KEYS`）—— 用户找功能靠它；
2. **分组小标题**（`GROUP`）；
3. **界面骨架与常用动作**（`COMMON`）—— 打开 / 搜索 / 保存 / 开始检测 …
4. **启动画面与「关于」的标语**（`SLOGAN`）。

查不到就**原样返回中文**，界面永远不会出现空白或 `?key?`。

⚠ 阿拉伯语与印地语
------------------
阿拉伯语是 RTL（从右往左）。本软件整窗布局是按 LTR 写死的
（`QHBoxLayout` + 侧栏在左），**没有做镜像**。所以阿拉伯语在这里只翻译**文字**，
版面方向仍是 LTR —— 这是刻意的取舍：真要把整窗镜像，得把每个 `addWidget` 的
顺序、`QSplitter.setSizes()`、以及所有自绘控件的坐标一起改，风险远大于收益。
`is_rtl()` 单独暴露出来，将来要做镜像时有据可依。
"""

# ---------------------------------------------------------------------------
# 语言表（顺序即界面下拉框顺序，简体中文排第一 —— 它是基准语言）
# ---------------------------------------------------------------------------
#: (代码, 自称, 中文名, 是否 RTL)
LANGUAGES = [
    ("zh_CN", "简体中文", "简体中文", False),
    ("en", "English", "英语", False),
    ("ja", "日本語", "日语", False),
    ("ko", "한국어", "韩语", False),
    ("es", "Español", "西班牙语", False),
    ("hi", "हिन्दी", "印地语", False),
    ("ar", "العربية", "阿拉伯语", True),
    ("pt", "Português", "葡萄牙语", False),
    ("ru", "Русский", "俄语", False),
    ("de", "Deutsch", "德语", False),
    ("fr", "Français", "法语", False),
    ("it", "Italiano", "意大利语", False),
    ("tr", "Türkçe", "土耳其语", False),
    ("nl", "Nederlands", "荷兰语", False),
    # 用户列举里写的是「19 种」但只点了 14 个名字，下面是补齐到 19 的五个
    # （都是本软件受众最可能用到的语种，按使用人数排序）。
    ("pl", "Polski", "波兰语", False),
    ("sv", "Svenska", "瑞典语", False),
    ("th", "ไทย", "泰语", False),
    ("vi", "Tiếng Việt", "越南语", False),
    ("id", "Bahasa Indonesia", "印尼语", False),
]

DEFAULT_LANG = "zh_CN"
BASE_LANG = "zh_CN"

_CODES = {c for c, _s, _n, _r in LANGUAGES}


def native_name(code) -> str:
    """语言的自称（下拉框里显示这个 —— 用户认自己的字，不认别人的字母）。"""
    for c, s, _n, _r in LANGUAGES:
        if c == code:
            return s
    return str(code or "")


def cn_name(code) -> str:
    """语言的简体中文名（设置页的说明文字、README 里用）。"""
    for c, _s, n, _r in LANGUAGES:
        if c == code:
            return n
    return str(code or "")


def normalize(code) -> str:
    """把任意来源的语言代码归一化；不认识的一律回落到基准语言。

    容错范围刻意放宽：`zh-Hans-CN` / `zh_CN.UTF-8` / `EN` / `en-US` 都能进对桶，
    因为配置可能是手改的、也可能是将来从系统区域读来的。
    """
    s = str(code or "").strip().replace("-", "_")
    if not s:
        return DEFAULT_LANG
    if s in _CODES:
        return s
    head = s.split("_")[0].split(".")[0].lower()
    if head in ("zh", "chs", "cht", "cn"):
        return "zh_CN"
    for c in _CODES:
        if c.lower() == head:
            return c
    return DEFAULT_LANG


def is_rtl(code) -> bool:
    """该语言是否从右往左（目前只有阿拉伯语）。**界面暂未镜像**，见模块头说明。"""
    return any(c == code and r for c, _s, _n, r in LANGUAGES)


# ---------------------------------------------------------------------------
# 词典
# ---------------------------------------------------------------------------
#: 侧栏导航 + 页面名（主页侧栏 / 工具窗导航 / 各页面标题共用同一份）
NAV_KEYS = {
    "zh_CN": {
        "首页": "首页", "最近播放": "最近播放", "我的收藏": "我的收藏",
        "智能推荐": "智能推荐", "文件夹": "文件夹", "合集": "合集",
        "全部": "全部", "演员库": "演员库", "导演库": "导演库",
        "分类": "分类", "媒体库": "媒体库", "数据统计": "数据统计",
        "实时状态": "实时状态",
    },
    "en": {
        "首页": "Home", "最近播放": "Recently Played", "我的收藏": "Favorites",
        "智能推荐": "Smart Picks", "文件夹": "Folders", "合集": "Collections",
        "全部": "All", "演员库": "Actors", "导演库": "Directors",
        "分类": "Categories", "媒体库": "Libraries", "数据统计": "Statistics",
        "实时状态": "Live Status",
    },
    "ja": {
        "首页": "ホーム", "最近播放": "最近再生", "我的收藏": "お気に入り",
        "智能推荐": "おすすめ", "文件夹": "フォルダ", "合集": "コレクション",
        "全部": "すべて", "演员库": "女優", "导演库": "監督",
        "分类": "カテゴリ", "媒体库": "ライブラリ", "数据统计": "統計",
        "实时状态": "リアルタイム状態",
    },
    "ko": {
        "首页": "홈", "最近播放": "최근 재생", "我的收藏": "즐겨찾기",
        "智能推荐": "추천", "文件夹": "폴더", "合集": "컬렉션",
        "全部": "전체", "演员库": "배우", "导演库": "감독",
        "分类": "분류", "媒体库": "라이브러리", "数据统计": "통계",
        "实时状态": "실시간 상태",
    },
    "es": {
        "首页": "Inicio", "最近播放": "Reproducidos", "我的收藏": "Favoritos",
        "智能推荐": "Recomendados", "文件夹": "Carpetas", "合集": "Colecciones",
        "全部": "Todo", "演员库": "Actrices", "导演库": "Directores",
        "分类": "Categorías", "媒体库": "Bibliotecas", "数据统计": "Estadísticas",
        "实时状态": "Estado en vivo",
    },
    "hi": {
        "首页": "होम", "最近播放": "हाल ही में चलाए", "我的收藏": "पसंदीदा",
        "智能推荐": "सुझाव", "文件夹": "फ़ोल्डर", "合集": "संग्रह",
        "全部": "सभी", "演员库": "अभिनेत्रियाँ", "导演库": "निर्देशक",
        "分类": "श्रेणियाँ", "媒体库": "लाइब्रेरी", "数据统计": "आँकड़े",
        "实时状态": "लाइव स्थिति",
    },
    "ar": {
        "首页": "الرئيسية", "最近播放": "شوهد حديثًا", "我的收藏": "المفضلة",
        "智能推荐": "مقترحات", "文件夹": "المجلدات", "合集": "المجموعات",
        "全部": "الكل", "演员库": "الممثلات", "导演库": "المخرجون",
        "分类": "التصنيفات", "媒体库": "المكتبات", "数据统计": "الإحصاءات",
        "实时状态": "الحالة المباشرة",
    },
    "pt": {
        "首页": "Início", "最近播放": "Reproduzidos", "我的收藏": "Favoritos",
        "智能推荐": "Recomendados", "文件夹": "Pastas", "合集": "Coleções",
        "全部": "Tudo", "演员库": "Atrizes", "导演库": "Diretores",
        "分类": "Categorias", "媒体库": "Bibliotecas", "数据统计": "Estatísticas",
        "实时状态": "Estado ao vivo",
    },
    "ru": {
        "首页": "Главная", "最近播放": "Недавние", "我的收藏": "Избранное",
        "智能推荐": "Рекомендации", "文件夹": "Папки", "合集": "Коллекции",
        "全部": "Все", "演员库": "Актрисы", "导演库": "Режиссёры",
        "分类": "Категории", "媒体库": "Библиотеки", "数据统计": "Статистика",
        "实时状态": "Состояние",
    },
    "de": {
        "首页": "Start", "最近播放": "Zuletzt gespielt", "我的收藏": "Favoriten",
        "智能推荐": "Empfehlungen", "文件夹": "Ordner", "合集": "Sammlungen",
        "全部": "Alle", "演员库": "Darstellerinnen", "导演库": "Regisseure",
        "分类": "Kategorien", "媒体库": "Bibliotheken", "数据统计": "Statistik",
        "实时状态": "Live-Status",
    },
    "fr": {
        "首页": "Accueil", "最近播放": "Récemment lus", "我的收藏": "Favoris",
        "智能推荐": "Suggestions", "文件夹": "Dossiers", "合集": "Collections",
        "全部": "Tout", "演员库": "Actrices", "导演库": "Réalisateurs",
        "分类": "Catégories", "媒体库": "Bibliothèques", "数据统计": "Statistiques",
        "实时状态": "État en direct",
    },
    "it": {
        "首页": "Home", "最近播放": "Riprodotti", "我的收藏": "Preferiti",
        "智能推荐": "Consigliati", "文件夹": "Cartelle", "合集": "Collezioni",
        "全部": "Tutti", "演员库": "Attrici", "导演库": "Registi",
        "分类": "Categorie", "媒体库": "Librerie", "数据统计": "Statistiche",
        "实时状态": "Stato live",
    },
    "tr": {
        "首页": "Ana Sayfa", "最近播放": "Son Oynatılan", "我的收藏": "Favoriler",
        "智能推荐": "Öneriler", "文件夹": "Klasörler", "合集": "Koleksiyonlar",
        "全部": "Tümü", "演员库": "Oyuncular", "导演库": "Yönetmenler",
        "分类": "Kategoriler", "媒体库": "Kitaplıklar", "数据统计": "İstatistikler",
        "实时状态": "Canlı Durum",
    },
    "nl": {
        "首页": "Start", "最近播放": "Onlangs gespeeld", "我的收藏": "Favorieten",
        "智能推荐": "Aanbevolen", "文件夹": "Mappen", "合集": "Collecties",
        "全部": "Alles", "演员库": "Actrices", "导演库": "Regisseurs",
        "分类": "Categorieën", "媒体库": "Bibliotheken", "数据统计": "Statistieken",
        "实时状态": "Livestatus",
    },
    "pl": {
        "首页": "Główna", "最近播放": "Ostatnio odtwarzane", "我的收藏": "Ulubione",
        "智能推荐": "Polecane", "文件夹": "Foldery", "合集": "Kolekcje",
        "全部": "Wszystko", "演员库": "Aktorki", "导演库": "Reżyserzy",
        "分类": "Kategorie", "媒体库": "Biblioteki", "数据统计": "Statystyki",
        "实时状态": "Stan na żywo",
    },
    "sv": {
        "首页": "Hem", "最近播放": "Senast spelade", "我的收藏": "Favoriter",
        "智能推荐": "Rekommenderat", "文件夹": "Mappar", "合集": "Samlingar",
        "全部": "Alla", "演员库": "Skådespelerskor", "导演库": "Regissörer",
        "分类": "Kategorier", "媒体库": "Bibliotek", "数据统计": "Statistik",
        "实时状态": "Live-status",
    },
    "th": {
        "首页": "หน้าแรก", "最近播放": "เล่นล่าสุด", "我的收藏": "รายการโปรด",
        "智能推荐": "แนะนำ", "文件夹": "โฟลเดอร์", "合集": "คอลเลกชัน",
        "全部": "ทั้งหมด", "演员库": "นักแสดงหญิง", "导演库": "ผู้กำกับ",
        "分类": "หมวดหมู่", "媒体库": "ไลบรารี", "数据统计": "สถิติ",
        "实时状态": "สถานะสด",
    },
    "vi": {
        "首页": "Trang chủ", "最近播放": "Vừa xem", "我的收藏": "Yêu thích",
        "智能推荐": "Gợi ý", "文件夹": "Thư mục", "合集": "Bộ sưu tập",
        "全部": "Tất cả", "演员库": "Diễn viên nữ", "导演库": "Đạo diễn",
        "分类": "Phân loại", "媒体库": "Thư viện", "数据统计": "Thống kê",
        "实时状态": "Trạng thái trực tiếp",
    },
    "id": {
        "首页": "Beranda", "最近播放": "Terbaru", "我的收藏": "Favorit",
        "智能推荐": "Rekomendasi", "文件夹": "Folder", "合集": "Koleksi",
        "全部": "Semua", "演员库": "Aktris", "导演库": "Sutradara",
        "分类": "Kategori", "媒体库": "Pustaka", "数据统计": "Statistik",
        "实时状态": "Status Langsung",
    },
}

#: 工具窗口导航（四分组 + 11 页）
TOOL_KEYS = {
    "zh_CN": {
        "工具": "工具",
        "基础工具": "基础工具", "数据优化": "数据优化",
        "智能检测": "智能检测", "数据分析": "数据分析",
        "个性化设置": "个性化设置", "服务管理": "服务管理", "手动修改": "手动修改",
        "演员刮削": "演员刮削", "智能推荐": "智能推荐", "标签优化": "标签优化",
        "重复检测": "重复检测", "演员检测": "演员检测", "图像检测": "图像检测",
        "画像概览": "画像概览", "数据与日志": "数据与日志",
    },
    "en": {
        "工具": "Tools",
        "基础工具": "Basics", "数据优化": "Data Tuning",
        "智能检测": "Smart Checks", "数据分析": "Analytics",
        "个性化设置": "Preferences", "服务管理": "Services", "手动修改": "Manual Edit",
        "演员刮削": "Actor Scraping", "智能推荐": "Smart Picks", "标签优化": "Tag Cleanup",
        "重复检测": "Duplicates", "演员检测": "Actor Check", "图像检测": "Image Check",
        "画像概览": "Profile Overview", "数据与日志": "Data & Logs",
    },
    "ja": {
        "工具": "ツール",
        "基础工具": "基本", "数据优化": "データ最適化",
        "智能检测": "スマート検査", "数据分析": "データ分析",
        "个性化设置": "環境設定", "服务管理": "サービス管理", "手动修改": "手動編集",
        "演员刮削": "女優スクレイピング", "智能推荐": "おすすめ", "标签优化": "タグ整理",
        "重复检测": "重複検出", "演员检测": "女優チェック", "图像检测": "画像チェック",
        "画像概览": "プロフィール概要", "数据与日志": "データとログ",
    },
    "ko": {
        "工具": "도구",
        "基础工具": "기본", "数据优化": "데이터 최적화",
        "智能检测": "스마트 검사", "数据分析": "데이터 분석",
        "个性化设置": "환경 설정", "服务管理": "서비스 관리", "手动修改": "수동 편집",
        "演员刮削": "배우 스크래핑", "智能推荐": "추천", "标签优化": "태그 정리",
        "重复检测": "중복 검사", "演员检测": "배우 검사", "图像检测": "이미지 검사",
        "画像概览": "프로필 개요", "数据与日志": "데이터 및 로그",
    },
    "es": {
        "工具": "Herramientas",
        "基础工具": "Básicos", "数据优化": "Optimización",
        "智能检测": "Comprobaciones", "数据分析": "Análisis",
        "个性化设置": "Preferencias", "服务管理": "Servicios", "手动修改": "Edición manual",
        "演员刮削": "Scraping de actrices", "智能推荐": "Recomendados", "标签优化": "Limpieza de etiquetas",
        "重复检测": "Duplicados", "演员检测": "Revisión de actrices", "图像检测": "Revisión de imágenes",
        "画像概览": "Resumen de perfil", "数据与日志": "Datos y registros",
    },
    "hi": {
        "工具": "उपकरण",
        "基础工具": "बुनियादी", "数据优化": "डेटा अनुकूलन",
        "智能检测": "स्मार्ट जाँच", "数据分析": "डेटा विश्लेषण",
        "个性化设置": "प्राथमिकताएँ", "服务管理": "सेवाएँ", "手动修改": "मैनुअल संपादन",
        "演员刮削": "अभिनेत्री स्क्रैपिंग", "智能推荐": "सुझाव", "标签优化": "टैग सफ़ाई",
        "重复检测": "दोहराव जाँच", "演员检测": "अभिनेत्री जाँच", "图像检测": "छवि जाँच",
        "画像概览": "प्रोफ़ाइल अवलोकन", "数据与日志": "डेटा और लॉग",
    },
    "ar": {
        "工具": "الأدوات",
        "基础工具": "أساسية", "数据优化": "تحسين البيانات",
        "智能检测": "فحوص ذكية", "数据分析": "تحليلات",
        "个性化设置": "التفضيلات", "服务管理": "الخدمات", "手动修改": "تحرير يدوي",
        "演员刮削": "جلب بيانات الممثلات", "智能推荐": "مقترحات", "标签优化": "تنظيف الوسوم",
        "重复检测": "كشف التكرار", "演员检测": "فحص الممثلات", "图像检测": "فحص الصور",
        "画像概览": "نظرة عامة", "数据与日志": "البيانات والسجلات",
    },
    "pt": {
        "工具": "Ferramentas",
        "基础工具": "Básicas", "数据优化": "Otimização",
        "智能检测": "Verificações", "数据分析": "Análises",
        "个性化设置": "Preferências", "服务管理": "Serviços", "手动修改": "Edição manual",
        "演员刮削": "Scraping de atrizes", "智能推荐": "Recomendados", "标签优化": "Limpeza de tags",
        "重复检测": "Duplicados", "演员检测": "Verificação de atrizes", "图像检测": "Verificação de imagens",
        "画像概览": "Resumo do perfil", "数据与日志": "Dados e registos",
    },
    "ru": {
        "工具": "Инструменты",
        "基础工具": "Основные", "数据优化": "Оптимизация данных",
        "智能检测": "Умные проверки", "数据分析": "Аналитика",
        "个性化设置": "Настройки", "服务管理": "Службы", "手动修改": "Правка вручную",
        "演员刮削": "Скрапинг актрис", "智能推荐": "Рекомендации", "标签优化": "Чистка тегов",
        "重复检测": "Поиск дублей", "演员检测": "Проверка актрис", "图像检测": "Проверка изображений",
        "画像概览": "Обзор профиля", "数据与日志": "Данные и логи",
    },
    "de": {
        "工具": "Werkzeuge",
        "基础工具": "Basis", "数据优化": "Datenoptimierung",
        "智能检测": "Intelligente Prüfungen", "数据分析": "Analysen",
        "个性化设置": "Einstellungen", "服务管理": "Dienste", "手动修改": "Manuelle Bearbeitung",
        "演员刮削": "Darstellerinnen-Scraping", "智能推荐": "Empfehlungen", "标签优化": "Tag-Bereinigung",
        "重复检测": "Duplikate", "演员检测": "Darstellerinnen-Prüfung", "图像检测": "Bildprüfung",
        "画像概览": "Profilübersicht", "数据与日志": "Daten & Protokolle",
    },
    "fr": {
        "工具": "Outils",
        "基础工具": "Essentiels", "数据优化": "Optimisation",
        "智能检测": "Vérifications", "数据分析": "Analyses",
        "个性化设置": "Préférences", "服务管理": "Services", "手动修改": "Édition manuelle",
        "演员刮削": "Scraping des actrices", "智能推荐": "Suggestions", "标签优化": "Nettoyage des tags",
        "重复检测": "Doublons", "演员检测": "Vérification des actrices", "图像检测": "Vérification des images",
        "画像概览": "Aperçu du profil", "数据与日志": "Données et journaux",
    },
    "it": {
        "工具": "Strumenti",
        "基础工具": "Base", "数据优化": "Ottimizzazione",
        "智能检测": "Controlli", "数据分析": "Analisi",
        "个性化设置": "Preferenze", "服务管理": "Servizi", "手动修改": "Modifica manuale",
        "演员刮削": "Scraping attrici", "智能推荐": "Consigliati", "标签优化": "Pulizia tag",
        "重复检测": "Duplicati", "演员检测": "Controllo attrici", "图像检测": "Controllo immagini",
        "画像概览": "Panoramica profilo", "数据与日志": "Dati e log",
    },
    "tr": {
        "工具": "Araçlar",
        "基础工具": "Temel", "数据优化": "Veri Optimizasyonu",
        "智能检测": "Akıllı Denetimler", "数据分析": "Analizler",
        "个性化设置": "Tercihler", "服务管理": "Hizmetler", "手动修改": "Elle Düzenleme",
        "演员刮削": "Oyuncu Kazıma", "智能推荐": "Öneriler", "标签优化": "Etiket Temizliği",
        "重复检测": "Yinelenenler", "演员检测": "Oyuncu Denetimi", "图像检测": "Görsel Denetimi",
        "画像概览": "Profil Özeti", "数据与日志": "Veri ve Günlükler",
    },
    "nl": {
        "工具": "Hulpmiddelen",
        "基础工具": "Basis", "数据优化": "Data-optimalisatie",
        "智能检测": "Slimme controles", "数据分析": "Analyses",
        "个性化设置": "Voorkeuren", "服务管理": "Diensten", "手动修改": "Handmatig bewerken",
        "演员刮削": "Actrices scrapen", "智能推荐": "Aanbevolen", "标签优化": "Labels opschonen",
        "重复检测": "Duplicaten", "演员检测": "Actrices controleren", "图像检测": "Afbeeldingen controleren",
        "画像概览": "Profieloverzicht", "数据与日志": "Data en logboeken",
    },
    "pl": {
        "工具": "Narzędzia",
        "基础工具": "Podstawowe", "数据优化": "Optymalizacja danych",
        "智能检测": "Inteligentne kontrole", "数据分析": "Analizy",
        "个性化设置": "Preferencje", "服务管理": "Usługi", "手动修改": "Edycja ręczna",
        "演员刮削": "Scraping aktorek", "智能推荐": "Polecane", "标签优化": "Czyszczenie tagów",
        "重复检测": "Duplikaty", "演员检测": "Kontrola aktorek", "图像检测": "Kontrola obrazów",
        "画像概览": "Przegląd profilu", "数据与日志": "Dane i dzienniki",
    },
    "sv": {
        "工具": "Verktyg",
        "基础工具": "Grundläggande", "数据优化": "Dataoptimering",
        "智能检测": "Smarta kontroller", "数据分析": "Analyser",
        "个性化设置": "Inställningar", "服务管理": "Tjänster", "手动修改": "Manuell redigering",
        "演员刮削": "Skrapa skådespelerskor", "智能推荐": "Rekommenderat", "标签优化": "Taggrensning",
        "重复检测": "Dubbletter", "演员检测": "Skådespelarkontroll", "图像检测": "Bildkontroll",
        "画像概览": "Profilöversikt", "数据与日志": "Data och loggar",
    },
    "th": {
        "工具": "เครื่องมือ",
        "基础工具": "พื้นฐาน", "数据优化": "ปรับแต่งข้อมูล",
        "智能检测": "ตรวจสอบอัจฉริยะ", "数据分析": "การวิเคราะห์",
        "个性化设置": "การตั้งค่า", "服务管理": "บริการ", "手动修改": "แก้ไขด้วยมือ",
        "演员刮削": "ดึงข้อมูลนักแสดง", "智能推荐": "แนะนำ", "标签优化": "ล้างแท็ก",
        "重复检测": "ตรวจหาซ้ำ", "演员检测": "ตรวจนักแสดง", "图像检测": "ตรวจรูปภาพ",
        "画像概览": "ภาพรวมโปรไฟล์", "数据与日志": "ข้อมูลและบันทึก",
    },
    "vi": {
        "工具": "Công cụ",
        "基础工具": "Cơ bản", "数据优化": "Tối ưu dữ liệu",
        "智能检测": "Kiểm tra thông minh", "数据分析": "Phân tích",
        "个性化设置": "Tùy chọn", "服务管理": "Dịch vụ", "手动修改": "Sửa thủ công",
        "演员刮削": "Cào dữ liệu diễn viên", "智能推荐": "Gợi ý", "标签优化": "Dọn thẻ",
        "重复检测": "Trùng lặp", "演员检测": "Kiểm tra diễn viên", "图像检测": "Kiểm tra ảnh",
        "画像概览": "Tổng quan hồ sơ", "数据与日志": "Dữ liệu và nhật ký",
    },
    "id": {
        "工具": "Alat",
        "基础工具": "Dasar", "数据优化": "Optimasi Data",
        "智能检测": "Pemeriksaan Cerdas", "数据分析": "Analitik",
        "个性化设置": "Preferensi", "服务管理": "Layanan", "手动修改": "Edit Manual",
        "演员刮削": "Scraping Aktris", "智能推荐": "Rekomendasi", "标签优化": "Pembersihan Tag",
        "重复检测": "Duplikat", "演员检测": "Pemeriksaan Aktris", "图像检测": "Pemeriksaan Gambar",
        "画像概览": "Ringkasan Profil", "数据与日志": "Data & Log",
    },
}

#: 常用动作 / 状态词（骨架按钮、开关标签、提示）
COMMON = {
    "zh_CN": {
        "确定": "确定", "取消": "取消", "保存": "保存", "关闭": "关闭",
        "删除": "删除", "编辑": "编辑", "添加": "添加", "开始检测": "开始检测",
        "停止": "停止", "全部": "全部", "外观": "外观", "关于": "关于",
        "语言": "语言", "界面语言": "界面语言", "外观与语言": "外观与语言",
        "切换界面语言（立即生效）": "切换界面语言（立即生效）",
        "搜索": "搜索", "设置": "设置", "工具": "工具",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）",
        "正在检查运行环境…": "正在检查运行环境…",
        "正在打开媒体索引…": "正在打开媒体索引…",
        "正在载入界面样式…": "正在载入界面样式…",
        "正在统计媒体库…": "正在统计媒体库…",
        "准备就绪": "准备就绪",
    },
    "en": {
        "确定": "OK", "取消": "Cancel", "保存": "Save", "关闭": "Close",
        "删除": "Delete", "编辑": "Edit", "添加": "Add", "开始检测": "Start Scan",
        "停止": "Stop", "全部": "All", "外观": "Appearance", "关于": "About",
        "语言": "Language", "界面语言": "Interface Language",
        "外观与语言": "Appearance & Language",
        "切换界面语言（立即生效）": "Switch interface language (applies instantly)",
        "搜索": "Search", "设置": "Settings", "工具": "Tools",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Search (Ctrl+K)   Title / Genre / Actor  (use @ for actor)",
        "正在检查运行环境…": "Checking environment…",
        "正在打开媒体索引…": "Opening media index…",
        "正在载入界面样式…": "Loading interface style…",
        "正在统计媒体库…": "Counting libraries…",
        "准备就绪": "Ready",
    },
    "ja": {
        "确定": "OK", "取消": "キャンセル", "保存": "保存", "关闭": "閉じる",
        "删除": "削除", "编辑": "編集", "添加": "追加", "开始检测": "検査開始",
        "停止": "停止", "全部": "すべて", "外观": "外観", "关于": "情報",
        "语言": "言語", "界面语言": "表示言語", "外观与语言": "外観と言語",
        "切换界面语言（立即生效）": "表示言語を切り替え（即時反映）",
        "搜索": "検索", "设置": "設定", "工具": "ツール",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "検索 (Ctrl+K)   タイトル / ジャンル / 出演者  （@ で出演者指定）",
        "正在检查运行环境…": "動作環境を確認しています…",
        "正在打开媒体索引…": "メディア索引を開いています…",
        "正在载入界面样式…": "インターフェースのスタイルを読み込んでいます…",
        "正在统计媒体库…": "ライブラリを集計しています…",
        "准备就绪": "準備完了",
    },
    "ko": {
        "确定": "확인", "取消": "취소", "保存": "저장", "关闭": "닫기",
        "删除": "삭제", "编辑": "편집", "添加": "추가", "开始检测": "검사 시작",
        "停止": "중지", "全部": "전체", "外观": "모양", "关于": "정보",
        "语言": "언어", "界面语言": "인터페이스 언어", "外观与语言": "모양 및 언어",
        "切换界面语言（立即生效）": "인터페이스 언어 변경(즉시 적용)",
        "搜索": "검색", "设置": "설정", "工具": "도구",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "검색 (Ctrl+K)   제목 / 장르 / 배우  (@ 로 배우 지정)",
        "正在检查运行环境…": "실행 환경 확인 중…",
        "正在打开媒体索引…": "미디어 색인 여는 중…",
        "正在载入界面样式…": "인터페이스 스타일 불러오는 중…",
        "正在统计媒体库…": "라이브러리 집계 중…",
        "准备就绪": "준비 완료",
    },
    "es": {
        "确定": "Aceptar", "取消": "Cancelar", "保存": "Guardar", "关闭": "Cerrar",
        "删除": "Eliminar", "编辑": "Editar", "添加": "Añadir", "开始检测": "Iniciar análisis",
        "停止": "Detener", "全部": "Todo", "外观": "Apariencia", "关于": "Acerca de",
        "语言": "Idioma", "界面语言": "Idioma de la interfaz",
        "外观与语言": "Apariencia e idioma",
        "切换界面语言（立即生效）": "Cambiar el idioma (se aplica al instante)",
        "搜索": "Buscar", "设置": "Ajustes", "工具": "Herramientas",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Buscar (Ctrl+K)   Título / Género / Actor  (usa @ para actor)",
        "正在检查运行环境…": "Comprobando el entorno…",
        "正在打开媒体索引…": "Abriendo el índice multimedia…",
        "正在载入界面样式…": "Cargando el estilo de la interfaz…",
        "正在统计媒体库…": "Contando las bibliotecas…",
        "准备就绪": "Listo",
    },
    "hi": {
        "确定": "ठीक", "取消": "रद्द करें", "保存": "सहेजें", "关闭": "बंद करें",
        "删除": "हटाएँ", "编辑": "संपादित करें", "添加": "जोड़ें", "开始检测": "जाँच शुरू करें",
        "停止": "रोकें", "全部": "सभी", "外观": "रूप", "关于": "परिचय",
        "语言": "भाषा", "界面语言": "इंटरफ़ेस भाषा", "外观与语言": "रूप और भाषा",
        "切换界面语言（立即生效）": "इंटरफ़ेस भाषा बदलें (तुरंत लागू)",
        "搜索": "खोजें", "设置": "सेटिंग्स", "工具": "उपकरण",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "खोजें (Ctrl+K)   शीर्षक / शैली / अभिनेता  (@ से अभिनेता)",
        "正在检查运行环境…": "वातावरण की जाँच हो रही है…",
        "正在打开媒体索引…": "मीडिया अनुक्रमणिका खोली जा रही है…",
        "正在载入界面样式…": "इंटरफ़ेस शैली लोड हो रही है…",
        "正在统计媒体库…": "लाइब्रेरी की गणना हो रही है…",
        "准备就绪": "तैयार",
    },
    "ar": {
        "确定": "موافق", "取消": "إلغاء", "保存": "حفظ", "关闭": "إغلاق",
        "删除": "حذف", "编辑": "تحرير", "添加": "إضافة", "开始检测": "بدء الفحص",
        "停止": "إيقاف", "全部": "الكل", "外观": "المظهر", "关于": "حول",
        "语言": "اللغة", "界面语言": "لغة الواجهة", "外观与语言": "المظهر واللغة",
        "切换界面语言（立即生效）": "تغيير لغة الواجهة (يُطبَّق فورًا)",
        "搜索": "بحث", "设置": "الإعدادات", "工具": "الأدوات",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "بحث (Ctrl+K)   العنوان / النوع / الممثل  (استخدم @ للممثل)",
        "正在检查运行环境…": "جارٍ فحص بيئة التشغيل…",
        "正在打开媒体索引…": "جارٍ فتح فهرس الوسائط…",
        "正在载入界面样式…": "جارٍ تحميل نمط الواجهة…",
        "正在统计媒体库…": "جارٍ إحصاء المكتبات…",
        "准备就绪": "جاهز",
    },
    "pt": {
        "确定": "OK", "取消": "Cancelar", "保存": "Guardar", "关闭": "Fechar",
        "删除": "Excluir", "编辑": "Editar", "添加": "Adicionar", "开始检测": "Iniciar análise",
        "停止": "Parar", "全部": "Tudo", "外观": "Aparência", "关于": "Sobre",
        "语言": "Idioma", "界面语言": "Idioma da interface",
        "外观与语言": "Aparência e idioma",
        "切换界面语言（立即生效）": "Alterar o idioma (aplica-se já)",
        "搜索": "Pesquisar", "设置": "Configurações", "工具": "Ferramentas",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Buscar (Ctrl+K)   Título / Gênero / Ator  (use @ para ator)",
        "正在检查运行环境…": "Verificando o ambiente…",
        "正在打开媒体索引…": "Abrindo o índice de mídia…",
        "正在载入界面样式…": "Carregando o estilo da interface…",
        "正在统计媒体库…": "Contando as bibliotecas…",
        "准备就绪": "Pronto",
    },
    "ru": {
        "确定": "ОК", "取消": "Отмена", "保存": "Сохранить", "关闭": "Закрыть",
        "删除": "Удалить", "编辑": "Изменить", "添加": "Добавить", "开始检测": "Начать проверку",
        "停止": "Остановить", "全部": "Все", "外观": "Оформление", "关于": "О программе",
        "语言": "Язык", "界面语言": "Язык интерфейса",
        "外观与语言": "Оформление и язык",
        "切换界面语言（立即生效）": "Сменить язык интерфейса (сразу)",
        "搜索": "Поиск", "设置": "Настройки", "工具": "Инструменты",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Поиск (Ctrl+K)   Название / Жанр / Актёр  (@ для актёра)",
        "正在检查运行环境…": "Проверка окружения…",
        "正在打开媒体索引…": "Открытие индекса медиатеки…",
        "正在载入界面样式…": "Загрузка стиля интерфейса…",
        "正在统计媒体库…": "Подсчёт библиотек…",
        "准备就绪": "Готово",
    },
    "de": {
        "确定": "OK", "取消": "Abbrechen", "保存": "Speichern", "关闭": "Schließen",
        "删除": "Löschen", "编辑": "Bearbeiten", "添加": "Hinzufügen", "开始检测": "Prüfung starten",
        "停止": "Stopp", "全部": "Alle", "外观": "Erscheinungsbild", "关于": "Über",
        "语言": "Sprache", "界面语言": "Oberflächensprache",
        "外观与语言": "Erscheinungsbild & Sprache",
        "切换界面语言（立即生效）": "Oberflächensprache wechseln (sofort wirksam)",
        "搜索": "Suchen", "设置": "Einstellungen", "工具": "Werkzeuge",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Suchen (Ctrl+K)   Titel / Genre / Darsteller  (@ für Darsteller)",
        "正在检查运行环境…": "Umgebung wird geprüft…",
        "正在打开媒体索引…": "Medienindex wird geöffnet…",
        "正在载入界面样式…": "Oberflächenstil wird geladen…",
        "正在统计媒体库…": "Bibliotheken werden gezählt…",
        "准备就绪": "Bereit",
    },
    "fr": {
        "确定": "OK", "取消": "Annuler", "保存": "Enregistrer", "关闭": "Fermer",
        "删除": "Supprimer", "编辑": "Modifier", "添加": "Ajouter", "开始检测": "Lancer l'analyse",
        "停止": "Arrêter", "全部": "Tout", "外观": "Apparence", "关于": "À propos",
        "语言": "Langue", "界面语言": "Langue de l'interface",
        "外观与语言": "Apparence et langue",
        "切换界面语言（立即生效）": "Changer la langue (effet immédiat)",
        "搜索": "Rechercher", "设置": "Paramètres", "工具": "Outils",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Rechercher (Ctrl+K)   Titre / Genre / Acteur  (@ pour acteur)",
        "正在检查运行环境…": "Vérification de l'environnement…",
        "正在打开媒体索引…": "Ouverture de l'index multimédia…",
        "正在载入界面样式…": "Chargement du style de l'interface…",
        "正在统计媒体库…": "Comptage des bibliothèques…",
        "准备就绪": "Prêt",
    },
    "it": {
        "确定": "OK", "取消": "Annulla", "保存": "Salva", "关闭": "Chiudi",
        "删除": "Elimina", "编辑": "Modifica", "添加": "Aggiungi", "开始检测": "Avvia analisi",
        "停止": "Interrompi", "全部": "Tutti", "外观": "Aspetto", "关于": "Informazioni",
        "语言": "Lingua", "界面语言": "Lingua dell'interfaccia",
        "外观与语言": "Aspetto e lingua",
        "切换界面语言（立即生效）": "Cambia lingua (effetto immediato)",
        "搜索": "Cerca", "设置": "Impostazioni", "工具": "Strumenti",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Cerca (Ctrl+K)   Titolo / Genere / Attore  (@ per attore)",
        "正在检查运行环境…": "Verifica dell'ambiente…",
        "正在打开媒体索引…": "Apertura dell'indice multimediale…",
        "正在载入界面样式…": "Caricamento dello stile dell'interfaccia…",
        "正在统计媒体库…": "Conteggio delle librerie…",
        "准备就绪": "Pronto",
    },
    "tr": {
        "确定": "Tamam", "取消": "İptal", "保存": "Kaydet", "关闭": "Kapat",
        "删除": "Sil", "编辑": "Düzenle", "添加": "Ekle", "开始检测": "Denetimi başlat",
        "停止": "Durdur", "全部": "Tümü", "外观": "Görünüm", "关于": "Hakkında",
        "语言": "Dil", "界面语言": "Arayüz dili", "外观与语言": "Görünüm ve dil",
        "切换界面语言（立即生效）": "Arayüz dilini değiştir (anında geçerli)",
        "搜索": "Ara", "设置": "Ayarlar", "工具": "Araçlar",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Ara (Ctrl+K)   Başlık / Tür / Oyuncu  (oyuncu için @)",
        "正在检查运行环境…": "Ortam kontrol ediliyor…",
        "正在打开媒体索引…": "Medya dizini açılıyor…",
        "正在载入界面样式…": "Arayüz stili yükleniyor…",
        "正在统计媒体库…": "Kitaplıklar sayılıyor…",
        "准备就绪": "Hazır",
    },
    "nl": {
        "确定": "OK", "取消": "Annuleren", "保存": "Opslaan", "关闭": "Sluiten",
        "删除": "Verwijderen", "编辑": "Bewerken", "添加": "Toevoegen", "开始检测": "Controle starten",
        "停止": "Stoppen", "全部": "Alles", "外观": "Weergave", "关于": "Over",
        "语言": "Taal", "界面语言": "Interfacetaal", "外观与语言": "Weergave en taal",
        "切换界面语言（立即生效）": "Interfacetaal wisselen (direct actief)",
        "搜索": "Zoeken", "设置": "Instellingen", "工具": "Hulpmiddelen",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Zoeken (Ctrl+K)   Titel / Genre / Acteur  (@ voor acteur)",
        "正在检查运行环境…": "Omgeving wordt gecontroleerd…",
        "正在打开媒体索引…": "Media-index wordt geopend…",
        "正在载入界面样式…": "Interface-stijl wordt geladen…",
        "正在统计媒体库…": "Bibliotheken worden geteld…",
        "准备就绪": "Gereed",
    },
    "pl": {
        "确定": "OK", "取消": "Anuluj", "保存": "Zapisz", "关闭": "Zamknij",
        "删除": "Usuń", "编辑": "Edytuj", "添加": "Dodaj", "开始检测": "Rozpocznij kontrolę",
        "停止": "Zatrzymaj", "全部": "Wszystko", "外观": "Wygląd", "关于": "Informacje",
        "语言": "Język", "界面语言": "Język interfejsu", "外观与语言": "Wygląd i język",
        "切换界面语言（立即生效）": "Zmień język (od razu)",
        "搜索": "Szukaj", "设置": "Ustawienia", "工具": "Narzędzia",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Szukaj (Ctrl+K)   Tytuł / Gatunek / Aktor  (@ dla aktora)",
        "正在检查运行环境…": "Sprawdzanie środowiska…",
        "正在打开媒体索引…": "Otwieranie indeksu multimediów…",
        "正在载入界面样式…": "Wczytywanie stylu interfejsu…",
        "正在统计媒体库…": "Zliczanie bibliotek…",
        "准备就绪": "Gotowe",
    },
    "sv": {
        "确定": "OK", "取消": "Avbryt", "保存": "Spara", "关闭": "Stäng",
        "删除": "Ta bort", "编辑": "Redigera", "添加": "Lägg till", "开始检测": "Starta kontroll",
        "停止": "Stoppa", "全部": "Alla", "外观": "Utseende", "关于": "Om",
        "语言": "Språk", "界面语言": "Gränssnittsspråk", "外观与语言": "Utseende och språk",
        "切换界面语言（立即生效）": "Byt språk (gäller direkt)",
        "搜索": "Sök", "设置": "Inställningar", "工具": "Verktyg",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Sök (Ctrl+K)   Titel / Genre / Skådespelare  (@ för skådespelare)",
        "正在检查运行环境…": "Kontrollerar miljön…",
        "正在打开媒体索引…": "Öppnar medieindex…",
        "正在载入界面样式…": "Laddar gränssnittsstil…",
        "正在统计媒体库…": "Räknar bibliotek…",
        "准备就绪": "Klar",
    },
    "th": {
        "确定": "ตกลง", "取消": "ยกเลิก", "保存": "บันทึก", "关闭": "ปิด",
        "删除": "ลบ", "编辑": "แก้ไข", "添加": "เพิ่ม", "开始检测": "เริ่มตรวจสอบ",
        "停止": "หยุด", "全部": "ทั้งหมด", "外观": "รูปลักษณ์", "关于": "เกี่ยวกับ",
        "语言": "ภาษา", "界面语言": "ภาษาของอินเทอร์เฟซ", "外观与语言": "รูปลักษณ์และภาษา",
        "切换界面语言（立即生效）": "เปลี่ยนภาษา (มีผลทันที)",
        "搜索": "ค้นหา", "设置": "การตั้งค่า", "工具": "เครื่องมือ",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "ค้นหา (Ctrl+K)   ชื่อเรื่อง / ประเภท / นักแสดง  (ใช้ @ ระบุนักแสดง)",
        "正在检查运行环境…": "กำลังตรวจสอบสภาพแวดล้อม…",
        "正在打开媒体索引…": "กำลังเปิดดัชนีสื่อ…",
        "正在载入界面样式…": "กำลังโหลดสไตล์อินเทอร์เฟซ…",
        "正在统计媒体库…": "กำลังนับไลบรารี…",
        "准备就绪": "พร้อมใช้งาน",
    },
    "vi": {
        "确定": "OK", "取消": "Hủy", "保存": "Lưu", "关闭": "Đóng",
        "删除": "Xóa", "编辑": "Sửa", "添加": "Thêm", "开始检测": "Bắt đầu kiểm tra",
        "停止": "Dừng", "全部": "Tất cả", "外观": "Giao diện", "关于": "Giới thiệu",
        "语言": "Ngôn ngữ", "界面语言": "Ngôn ngữ giao diện",
        "外观与语言": "Giao diện và ngôn ngữ",
        "切换界面语言（立即生效）": "Đổi ngôn ngữ (áp dụng ngay)",
        "搜索": "Tìm kiếm", "设置": "Cài đặt", "工具": "Công cụ",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Tìm kiếm (Ctrl+K)   Tên phim / Thể loại / Diễn viên  (dùng @ cho diễn viên)",
        "正在检查运行环境…": "Đang kiểm tra môi trường…",
        "正在打开媒体索引…": "Đang mở chỉ mục phương tiện…",
        "正在载入界面样式…": "Đang tải kiểu giao diện…",
        "正在统计媒体库…": "Đang đếm thư viện…",
        "准备就绪": "Sẵn sàng",
    },
    "id": {
        "确定": "OK", "取消": "Batal", "保存": "Simpan", "关闭": "Tutup",
        "删除": "Hapus", "编辑": "Edit", "添加": "Tambah", "开始检测": "Mulai periksa",
        "停止": "Hentikan", "全部": "Semua", "外观": "Tampilan", "关于": "Tentang",
        "语言": "Bahasa", "界面语言": "Bahasa antarmuka", "外观与语言": "Tampilan & Bahasa",
        "切换界面语言（立即生效）": "Ganti bahasa (langsung berlaku)",
        "搜索": "Cari", "设置": "Pengaturan", "工具": "Alat",
        "搜索 (Ctrl+K)   片名 / 类型 / 演员  （用 @ 指定演员）": "Cari (Ctrl+K)   Judul / Genre / Aktor  (gunakan @ untuk aktor)",
        "正在检查运行环境…": "Memeriksa lingkungan…",
        "正在打开媒体索引…": "Membuka indeks media…",
        "正在载入界面样式…": "Memuat gaya antarmuka…",
        "正在统计媒体库…": "Menghitung pustaka…",
        "准备就绪": "Siap",
    },
}

#: 标语（启动画面 + 「关于」共用；中文/英文的真源仍在 version.py，这里只补其它语种）
SLOGAN = {
    "zh_CN": "所有流明 · 尽收盒中",
    "en": "Every lumen, in one crate.",
    "ja": "すべてのルーメンを、ひとつの箱に。",
    "ko": "모든 빛을, 하나의 상자에.",
    "es": "Cada lumen, en una caja.",
    "hi": "हर ल्यूमेन, एक डिब्बे में।",
    "ar": "كل لومن، في صندوق واحد.",
    "pt": "Cada lúmen, numa caixa.",
    "ru": "Каждый люмен — в одном ящике.",
    "de": "Jedes Lumen in einer Kiste.",
    "fr": "Chaque lumen, dans un coffret.",
    "it": "Ogni lumen, in una cassa.",
    "tr": "Her lümen, tek bir kutuda.",
    "nl": "Elk lumen, in één kist.",
    "pl": "Każdy lumen, w jednej skrzyni.",
    "sv": "Varje lumen, i en låda.",
    "th": "ทุกลูเมน ในกล่องเดียว",
    "vi": "Mọi lumen, trong một chiếc hộp.",
    "id": "Setiap lumen, dalam satu kotak.",
}

_DICTS = (NAV_KEYS, TOOL_KEYS, COMMON)

#: 全局当前语言（模块级单例）。改它之后界面要自己重刷 —— 见 `set_lang()` 说明。
_current = DEFAULT_LANG


def get_lang() -> str:
    """当前界面语言。"""
    return _current


def set_lang(code) -> str:
    """设置当前界面语言并返回归一化后的代码。

    ⚠ 这里**只改模块级变量**，不负责刷新已建好的界面 ——
    调用方（`SettingsDialog._apply_language`）改完要去通知主窗重建。
    这么切分是因为「刷新界面」是本项目的敏感动作（v1.27.0 踩过侧栏重建把
    运行中 QThread 连带销毁、进程直接 abort 的坑），必须由唯一入口做。
    """
    global _current
    _current = normalize(code)
    return _current


def tr(text) -> str:
    """翻译一条界面文案。

    查不到就**原样返回中文** —— 这是刻意的降级，不是遗漏：
    本项目 1900+ 条中文里绝大多数是业务细节（算法说明、免责声明），
    强行机器翻译会把「真机实测结论」这类内容翻错，反而误导用户。
    """
    s = str(text if text is not None else "")
    if not s or _current == BASE_LANG:
        return s
    for d in _DICTS:
        table = d.get(_current)
        if table and s in table:
            return table[s]
    return s


def tr_slogan() -> str:
    """当前语言的标语（中文仍取 version.SLOGAN_CN 的真源，这里只作回退）。"""
    return SLOGAN.get(_current) or SLOGAN[BASE_LANG]


def lang_names():
    """下拉框用的 `[(代码, 自称), …]`，顺序即 `LANGUAGES`。"""
    return [(c, s) for c, s, _n, _r in LANGUAGES]


def coverage() -> dict:
    """诊断用：每种语言在三个词典里分别命中多少条（缺的就是会显示中文的部分）。"""
    out = {}
    for code, _s, _n, _r in LANGUAGES:
        out[code] = {name: len(d.get(code, {})) for name, d in
                     zip(("nav", "tool", "common"), _DICTS)}
    return out
