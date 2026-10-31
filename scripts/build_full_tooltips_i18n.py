# -*- coding: utf-8 -*-
"""
Генератор полной базы интернационализации i18n для тултипов (AI Smart Tooltips).
Формирует точные переводы на английский (EN), украинский (UK) и иврит (HE)
для всех 156 ключей подсказок и интегрирует их в ru.json, en.json, uk.json, he.json.
Файл: scripts/build_full_tooltips_i18n.py
Updated: 2026-10-31 16:55:00
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LOCALES_DIR = Path("apps/windows/api/webgui/locales")
RU_PATH = LOCALES_DIR / "ru.json"
EN_PATH = LOCALES_DIR / "en.json"
UK_PATH = LOCALES_DIR / "uk.json"
HE_PATH = LOCALES_DIR / "he.json"
RU_ALL_PATH = LOCALES_DIR / "all_tooltips_ru.json"
ru_all = json.load(open(RU_ALL_PATH, encoding="utf-8"))

# Категории
CAT_I18N = {
    "Рабочая область": {"en": "Workspace", "uk": "Робоча область", "he": "מרחב עבודה"},
    "База знаний": {"en": "Knowledge Base", "uk": "База знань", "he": "מאגר ידע"},
    "Версионирование": {"en": "Versioning", "uk": "Версіонування", "he": "ניהול גרסאות"},
    "Обучение": {"en": "Tutorial", "uk": "Навчання", "he": "הדרכה"},
    "Защита от вымогателей": {"en": "Ransomware Protection", "uk": "Захист від вимагачів", "he": "הגנה מפני כופר"},
    "Снижение поверхности атак": {"en": "Attack Surface Reduction", "uk": "Зниження поверхні атак", "he": "צמצום משטח התקפה"},
    "Политики исключений": {"en": "Exclusion Policies", "uk": "Політики виключень", "he": "מדיניות חריגות"},
    "Журнал инцидентов": {"en": "Incident Log", "uk": "Журнал інцидентів", "he": "יומן תקריות"},
    "Поведенческий анализ": {"en": "Behavioral Analysis", "uk": "Поведінковий аналіз", "he": "ניתוח התנהגותי"},
    "События и аудит": {"en": "Events & Audit", "uk": "Події та аудит", "he": "אירועים וביקורת"},
    "Диагностика": {"en": "Diagnostics", "uk": "Діагностика", "he": "אבחון"},
    "Антивирусное сканирование": {"en": "Antivirus Scan", "uk": "Антивірусне сканування", "he": "סריקת אנטי-וירוס"},
    "Обновление определений": {"en": "Signatures Update", "uk": "Оновлення визначень", "he": "עדכון חתימות"},
    "Защита реального времени": {"en": "Real-time Protection", "uk": "Захист реального часу", "he": "הגנה בזמן אמת"},
    "Облачная защита": {"en": "Cloud Protection", "uk": "Хмарний захист", "he": "הגנת ענן"},
    "Защитник Windows": {"en": "Windows Defender", "uk": "Захисник Windows", "he": "Windows Defender"},
    "Сводная панель": {"en": "Summary Dashboard", "uk": "Зведена панель", "he": "לוח בקרה מרכזי"},
    "Системные журналы": {"en": "System Logs", "uk": "Системні журнали", "he": "יומני מערכת"},
    "Анализ активности": {"en": "Activity Analysis", "uk": "Аналіз активності", "he": "ניתוח פעילות"},
    "Управление питанием": {"en": "Power Management", "uk": "Керування живленням", "he": "ניהול צריכת חשמל"},
    "Безопасность": {"en": "Security", "uk": "Безпека", "he": "אבטחה"},
    "Анализ сбоев": {"en": "Failure Analysis", "uk": "Аналіз збоїв", "he": "ניתוח תקלות"},
    "Режим аналитики": {"en": "Analytics Mode", "uk": "Режим аналітики", "he": "מצב ניתוח"},
    "Категория сбоев": {"en": "Failure Category", "uk": "Категорія збоїв", "he": "קטגוריית תקלות"},
    "Управление службой": {"en": "Service Control", "uk": "Керування службою", "he": "בקרת שירות"},
    "Инвентаризация": {"en": "Inventory", "uk": "Інвентаризація", "he": "מלאי מערכת"},
    "Пакетные менеджеры": {"en": "Package Managers", "uk": "Пакетні менеджери", "he": "מנהלי חבילות"},
    "Оптимизация": {"en": "Optimization", "uk": "Оптимізація", "he": "אופטימיזציה"},
    "Прозрачность": {"en": "Transparency", "uk": "Прозорість", "he": "שקיפות תוכנה"},
    "Мониторинг ресурсов": {"en": "Resource Monitoring", "uk": "Моніторинг ресурсів", "he": "ניטור משאבים"},
    "Сетевой мониторинг": {"en": "Network Monitoring", "uk": "Мережевий моніторинг", "he": "ניטור רשת"},
    "Управление ПО": {"en": "Software Management", "uk": "Керування ПЗ", "he": "ניהול תוכנה"},
    "Фильтрация": {"en": "Filtering", "uk": "Фільтрація", "he": "סינון"},
    "Учетные записи": {"en": "User Accounts", "uk": "Облікові записи", "he": "חשבונות משתמש"},
    "Группы безопасности": {"en": "Security Groups", "uk": "Групи безпеки", "he": "קבוצות אבטחה"},
    "Аудит безопасности": {"en": "Security Audit", "uk": "Аудит безпеки", "he": "ביקורת אבטחה"},
    "Политики безопасности": {"en": "Security Policies", "uk": "Політики безпеки", "he": "מדיניות אבטחה"},
    "Инспектор процессов": {"en": "Process Inspector", "uk": "Інспектор процесів", "he": "מפקח תהליכים"},
    "Каталог системы": {"en": "System Catalog", "uk": "Каталог системи", "he": "קטלוג מערכת"},
    "Управление доступом": {"en": "Access Control (ACL)", "uk": "Керування доступом (ACL)", "he": "בקרת גישה (ACL)"},
    "Управление пользователями": {"en": "User Management", "uk": "Керування користувачами", "he": "ניהול משתמשים"},
    "Приватность": {"en": "Privacy", "uk": "Приватність", "he": "פרטיות"},
    "Резервное копирование": {"en": "Backup", "uk": "Резервне копіювання", "he": "גיבוי ושחזור"},
    "Удаленный доступ": {"en": "Remote Access", "uk": "Віддалений доступ", "he": "גישה מרחוק"},
    "Целостность": {"en": "Integrity", "uk": "Цілісність", "he": "תקינות ושלמות"},
    "Безопасность ACL": {"en": "ACL Security", "uk": "Безпека ACL", "he": "אבטחת ACL"},
    "Диспетчер процессов": {"en": "Task Manager", "uk": "Диспетчер процесів", "he": "מנהל המשימות"},
    "Навигация": {"en": "Navigation", "uk": "Навігація", "he": "ניווט"},
    "Управление деревом": {"en": "Tree Controls", "uk": "Керування деревом", "he": "בקרת עץ"},
    "Настройки": {"en": "Settings", "uk": "Налаштування", "he": "הגדרות"},
    "Файловый монитор": {"en": "File Watcher", "uk": "Файловий монітор", "he": "ניטור קבצים"},
    "Аудит утечек": {"en": "Leak Hunter", "uk": "Аудит витоків", "he": "איתור דליפות משאבים"},
    "Системный интерфейс": {"en": "System UI", "uk": "Системний інтерфейс", "he": "ממשק מערכת"},
    "Оболочка Windows": {"en": "Windows Shell", "uk": "Оболонка Windows", "he": "מעטפת Windows"},
    "Системный узел": {"en": "System Host", "uk": "Системний вузол", "he": "מארח מערכת"},
    "Фоновые задачи": {"en": "Background Tasks", "uk": "Фонові завдання", "he": "משימות רקע"},
    "Подсистема безопасности": {"en": "Security Subsystem", "uk": "Підсистема безпеки", "he": "מערך אבטחת מידע"},
    "Подсистема Win32": {"en": "Win32 Subsystem", "uk": "Підсистема Win32", "he": "תת-מערכת Win32"},
    "Диспетчер служб": {"en": "Service Manager", "uk": "Диспетчер служб", "he": "מנהל שירותים"},
    "Инициализация сессий": {"en": "Session Manager", "uk": "Ініціалізація сесій", "he": "מנהל הפעלות"},
    "Вход в систему": {"en": "Windows Logon", "uk": "Вхід до системи", "he": "כניסה למערכת"},
    "Инициализация ОС": {"en": "System Init", "uk": "Ініціалізація ОС", "he": "אתחול מערכת"},
    "Командная строка": {"en": "Command Shell", "uk": "Командний рядок", "he": "שורת פקודה"},
    "Хост консоли": {"en": "Console Host", "uk": "Хост консолі", "he": "מארח קונסולה"},
    "Антивирусная защита": {"en": "Antivirus Engine", "uk": "Антивірусний захист", "he": "מנוע אנטי-וירוס"},
    "Брокер UWP": {"en": "Runtime Broker", "uk": "Брокер UWP", "he": "מתווך זמן ריצה"},
    "Индексация": {"en": "Search Indexer", "uk": "Індексація", "he": "אינדוקס חיפוש"},
    "Диспетчер печати": {"en": "Print Spooler", "uk": "Диспетчер друку", "he": "שירות הדפסה"},
    "Ядро Windows": {"en": "Windows Kernel", "uk": "Ядро Windows", "he": "ליבת Windows"},
    "Реестр Windows": {"en": "Windows Registry", "uk": "Реєстр Windows", "he": "רישום Windows"},
    "Сетевой туннель": {"en": "Network Tunnel", "uk": "Мережевий тунель", "he": "מנהרת רשת"},
    "Ввод текста": {"en": "Text Input", "uk": "Введення тексту", "he": "קלט טקסט"},
    "Аудит ПО": {"en": "Software Audit", "uk": "Аудит ПЗ", "he": "ביקורת תוכנה"},
    "Автозапуск": {"en": "Startup", "uk": "Автозапуск", "he": "הפעלה אוטומטית"},
    "Аппаратный мониторинг": {"en": "Hardware Monitoring", "uk": "Апаратний моніторинг", "he": "ניטור חומרה"},
    "Справка": {"en": "Help", "uk": "Довідка", "he": "עזרה"}
}

def get_cat(ru_cat, lang):
    return CAT_I18N.get(ru_cat, {}).get(lang, ru_cat)

# Основные языковые словари (en, uk, he)
BASE_TRANSLATIONS = {
    "workspace": {
        "en": ("Workspace", "Project workspace containing linked files, context sources, fact base, and technical documentation."),
        "uk": ("Робочий простір", "Робоча область проєкту з пов'язаними файлами, джерелами контексту, базою фактів і документацією."),
        "he": ("מרחב עבודה", "סביבת עבודה של הפרויקט עם קבצים מקושרים, מקורות הקשר, מאגר עובדות ותיעוד.")
    },
    "qa": {
        "en": ("Q&A Knowledge Base", "Semantic question-answering module powered by vector storage and knowledge retrieval."),
        "uk": ("Запитання та відповіді (Q&A)", "Семантичний модуль запитань та відповідей на базі векторного сховища знань."),
        "he": ("שאלות ותשובות (Q&A)", "מודול שאלות ותשובות סמנטי המבוסס על אחסון וקטורי ואחזור ידע.")
    },
    "commits": {
        "en": ("Commit History", "Interactive repository commit log with change analytics and code diff summaries."),
        "uk": ("Історія комітів", "Інтерактивна стрічка комітів репозиторію з аналізом змін та описом дифів."),
        "he": ("היסטוריית שינויים (Commits)", "פיד שינויים אינטראקטיבי של המאגר עם ניתוח שינויים ותיאורי הבדלים.")
    },
    "system_tour": {
        "en": ("System Tour", "Interactive step-by-step walkthrough of core administrator screens and web interface tools."),
        "uk": ("Тур системою", "Покроковий інтерактивний гід ключовими екранами та інструментами веб-інтерфейсу."),
        "he": ("סיור במערכת", "מדריך אינטראקטיבי שלב אחר שלב במסכי הניהול המרכזיים וכלי הממשק.")
    },
    "cfa": {
        "en": ("Ransomware / CFA", "Controlled Folder Access (CFA) guards against ransomware by blocking unauthorized file modifications in protected user and system folders."),
        "uk": ("Ransomware / CFA", "Controlled Folder Access (CFA) захищає від програм-вимагачів, блокуючи несанкціоновані зміни в захищених папках користувача та системи."),
        "he": ("הגנה מפני כופר / CFA", "גישה מבוקרת לתיקיות (CFA) מגינה מפני תוכנות כופר על ידי חסימת שינויים בלתי מורשים בתיקיות מוגנות.")
    },
    "asr": {
        "en": ("ASR Rules", "Attack Surface Reduction (ASR) rules block common threat vectors: malicious Office macros, unauthorized scripts, and code injection."),
        "uk": ("Правила ASR", "Правила зниження поверхні атак (ASR) блокують типові вектори загроз: шкідливі макроси Office, ненадійні скрипти та ін'єкції коду."),
        "he": ("כללי ASR", "כללי צמצום משטח התקפה (ASR) חוסמים וקטורי איומים נפוצים כגון מאקרו זדוני של Office, סקריפטים לא מורשים והזרקת קוד.")
    },
    "exclusions": {
        "en": ("Defender Exclusions", "List of paths, file extensions, and processes excluded from real-time antivirus scans. Requires regular auditing."),
        "uk": ("Виключення Defender", "Список шляхів, розширень та процесів, виключених зі сканування в реальному часі. Потребує регулярного аудиту."),
        "he": ("חריגות Defender", "רשימת נתיבים, סיומות ותהליכים המוחרגים מסריקה בזמן אמת. דורש ביקורת קבועה למניעת הפעלת נוזקות.")
    },
    "threats": {
        "en": ("Threats & Quarantine", "Centralized repository of detected threats and quarantined files, allowing safe recovery or permanent deletion."),
        "uk": ("Загрози та Карантин", "Централізований журнал виявлених загроз та ізольоване сховище (Карантин) для безпечного відновлення чи видалення."),
        "he": ("איומים והסגר", "יומן מרכזי של איומים שזוהו וקבצים בהסגר, המאפשר שחזור בטוח של קבצים תקינים או מחיקה לצמיתות.")
    },
    "procs": {
        "en": ("Process Tree / Fileless", "Behavioral process tree monitoring and detection of fileless malware abusing legitimate Windows utilities (LOLBins)."),
        "uk": ("Дерево Процесів / Fileless", "Поведінковий моніторинг запущених процесів та виявлення безфайлових атак через легітимні утиліти Windows (LOLBins)."),
        "he": ("עץ תהליכים / ללא קבצים", "ניטור התנהגותי של עץ תהליכים וזיהוי תקיפות ללא קבצים (Fileless) המנצלות כלי מערכת לגיטימיים של Windows.")
    },
    "events": {
        "en": ("Security Events", "Windows Defender event stream (Event IDs 1116, 1117, 5001, etc.) tracking detections, blocks, and definition updates."),
        "uk": ("Журнал Подій", "Стрічка подій безпеки Захисника Windows (Event ID 1116, 1117, 5001 тощо), що фіксує виявлення, блокування та оновлення."),
        "he": ("יומן אירועי אבטחה", "פיד אירועי אבטחה של Windows Defender (מזהים 1116, 1117, 5001 ועוד) העוקב אחר זיהויים, חסימות ועדכונים.")
    },
    "diag": {
        "en": ("Antivirus Diagnostics", "Deep health verification of Windows antivirus engine, MpCmdRun configuration, definition age, and scan status."),
        "uk": ("Комплексна Діагностика", "Глибока перевірка стану антивірусного рушія Windows, конфігурації MpCmdRun, актуальності сигнатур та сканерів."),
        "he": ("אבחון אנטי-וירוס", "בדיקת תקינות מקיפה של מנוע האנטי-וירוס, תצורת MpCmdRun, עדכניות מאגרי החתימות ומצב הסורקים.")
    },
    "quick_scan": {
        "en": ("Quick Scan", "Executes an express scan of RAM, startup programs, and active system folders for malicious code."),
        "uk": ("Швидке сканування", "Запуск експрес-сканування оперативної пам'яті, автозапуску та системних папок на наявність активних загроз."),
        "he": ("סריקה מהירה", "הפעלת סריקה מהירה של זיכרון RAM, תוכניות הפעלה אוטומטית ותיקיות מערכת לאיתור קוד זדוני.")
    },
    "full_scan": {
        "en": ("Full Scan", "Deep scan of all storage drives, archive files, system libraries, and user documents. Recommended on suspected infection."),
        "uk": ("Повне сканування", "Глибока перевірка всіх дисків, архівів, системних бібліотек та файлів. Рекомендується при підозрі на зараження."),
        "he": ("סריקה מלאה", "סריקה מעמיקה של כל הכוננים, קובצי ארכיון, ספריות מערכת וקבצי משתמש. מומלץ בחשד להדבקה.")
    },
    "update_sigs": {
        "en": ("Update Signatures", "Forces download and installation of the newest antivirus definitions from Microsoft Security Intelligence."),
        "uk": ("Оновлення сигнатур", "Примусове завантаження та встановлення найновіших антивірусних баз із Microsoft Security Intelligence."),
        "he": ("עדכון חתימות", "הורדה והתקנה יזומה של מאגרי חתימות איומים עדכניים משרתי Microsoft Security Intelligence.")
    },
    "realtime": {
        "en": ("Real-time Protection", "Core file system minifilter driver (WdFilter) intercepting and validating all file read and write requests."),
        "uk": ("Захист у реальному часі", "Основний фільтр файлової системи (WdFilter), що перехоплює та перевіряє всі операції читання й запису файлів."),
        "he": ("הגנה בזמן אמת", "מסנן מערכת קבצים ראשי (WdFilter) המיירט ובודק את כל פעולות הקריאה והכתיבה בזמן אמת.")
    },
    "cloud_tamper": {
        "en": ("Cloud & Tamper Protection", "Cloud-delivered heuristic analysis (MAPS) combined with Tamper Protection preventing unauthorized security policy alterations."),
        "uk": ("Хмарний захист та Tamper", "Хмарна евристика (MAPS) та захист від несанкціонованих змін (Tamper Protection), що блокує спроби вимкнення антивірусу."),
        "he": ("הגנת ענן ו-Tamper", "ניתוח היוריסטי בענן (MAPS) והגנה מפני שיבוש (Tamper Protection) החוסמת שינויים בלתי מורשים בהגדרות אבטחה.")
    },
    "overview": {
        "en": ("Overview & Services", "Consolidated telemetry view of Windows Defender services, active protection components, and signature versions."),
        "uk": ("Огляд та служби", "Зведений моніторинг стану служб Windows Defender, активних компонентів захисту та версій антивірусних баз."),
        "he": ("סקירה ושירותים", "לוח בקרה מרוכז לניטור מצב שירותי Windows Defender, רכיבי הגנה פעילים וגרסאות חתימות האיומים.")
    },
    "summary-dashboard": {
        "en": ("Summary Dashboard", "System health overview consolidating crashes, critical system events, hardware failures, and power anomalies."),
        "uk": ("Зведена панель", "Зведений огляд надійності системи: системні збої, критичні події, апаратні помилки та аномалії живлення."),
        "he": ("לוח בקרה מרכזי", "מבט כולל על בריאות המערכת המרכז קריסות, אירועי מערכת קריטיים, תקלות חומרה ואנומליות צריכת חשמל.")
    },
    "event-logs": {
        "en": ("Windows Event Logs", "Structured event viewer inspecting System, Application, and Security channels with diagnostic filtering."),
        "uk": ("Системні Журнали", "Структурований перегляд системних подій каналів System, Application та Security з діагностичними фільтрами."),
        "he": ("יומני אירועים", "מציג אירועים מובנה לבדיקת ערוצי System, Application ו-Security עם סינון מתקדם.")
    },
    "activity": {
        "en": ("Host Activity", "Live telemetry of active processes, resource consumption, background threads, and execution frequency."),
        "uk": ("Активність Хоста", "Телеметрія активних процесів, споживання ресурсів, фонових потоків та частоти запусків у реальному часі."),
        "he": ("פעילות המערכת", "טלמטריה בזמן אמת של תהליכים פעילים, צריכת משאבים, תהליכוני רקע ותדירות הפעלות.")
    },
    "power-lifecycle": {
        "en": ("Power & Lifecycle", "Audit of sleep states, ACPI power events, thermal throttling triggers, unexpected shutdowns, and restarts."),
        "uk": ("Живлення та Стан", "Аудит режимів сну, подій живлення ACPI, термального тротлінгу, раптових вимкнень та перезавантажень."),
        "he": ("צריכת חשמל ומחזור חיים", "ביקורת מצבי שינה, אירועי חשמל ACPI, הפעלת תרוטלינג, כיבויים בלתי צפויים ואתחולים.")
    },
    "defender-logs": {
        "en": ("Defender Logs", "Consolidated audit of security detections, malware quarantining, and network inspection activity."),
        "uk": ("Журнали Defender", "Зведений аудит виявлених загроз, ізоляції шкідливого ПЗ та подій мережевого інспектування."),
        "he": ("יומני Defender", "יומן מרוכז של זיהויי אבטחה, בידוד נוזקות ופעילות בדיקת רשת של האנטי-וירוס.")
    },
    "forensics": {
        "en": ("System Forensics", "Detailed crash dumps examination, BSOD minidump diagnostics, and forensic memory inspection."),
        "uk": ("Форензика Системи", "Глибокий аналіз аварійних дампів пам'яті, діагностика BSOD та хронологія системних збоїв."),
        "he": ("פורנזיקה של המערכת", "ניתוח מפורט של קבצי Dump, אבחון קריסות מסך כחול (BSOD) ובדיקת זיכרון לחקירת תקלות.")
    },
    "mode-live": {
        "en": ("Live Stream Mode", "Real-time stream of incoming events and process activity with continuous auto-refresh."),
        "uk": ("Режим Live Stream", "Потік подій та активності процесів у реальному часі з безперервним автоматичним оновленням."),
        "he": ("מצב זרם חי (Live)", "פיד אירועים ופעילות תהליכים בזמן אמת עם רענון אוטומטי רציף.")
    },
    "mode-audit": {
        "en": ("Smart Audit Mode", "Intelligent deduplication and pattern recognition across event bursts and system errors."),
        "uk": ("Режим Смарт-Аудиту", "Інтелектуальна дедуплікація та розпізнавання патернів серед сплесків подій і системних помилок."),
        "he": ("מצב ביקורת חכמה", "ניתוח חכם, זיהוי דפוסים ומניעת כפילויות של גלי אירועים ושגיאות מערכת.")
    },
    "mode-rag": {
        "en": ("RAG Search Mode", "Semantic retrieval and context search across indexed system documentation and error catalogs."),
        "uk": ("Режим RAG Пошуку", "Семантичний пошук та вибірка контексту з індексованої системної документації та каталогів помилок."),
        "he": ("מצב חיפוש RAG", "אחזור סמנטי וחיפוש הקשרי מתוך תיעוד המערכת ומאגרי שגיאות מאונדקסים.")
    },
    "mode-incidents": {
        "en": ("Incidents Mode", "Cluster view of recurring failures grouped by subsystem, impact severity, and root cause."),
        "uk": ("Режим Інцидентів", "Групування повторюваних збоїв за підсистемами, критичністю та першопричинами."),
        "he": ("מצב תקריות", "מבט מקובץ על תקלות חוזרות לפי תת-מערכת, רמת חומרה ושורש הבעיה.")
    },
    "mode-timeline": {
        "en": ("Timeline Mode", "Chronological heatmaps and event frequency distributions visualizing peak incident periods."),
        "uk": ("Режим Таймлайну", "Хронологічна теплова карта та розподіл частоти подій для виявлення пікових періодів збоїв."),
        "he": ("מצב ציר זמן", "מפת חום כרונולוגית וחלוקת תדירות אירועים לזיהוי תקופות עומס ותקלות שיא.")
    },
    "mode-errors": {
        "en": ("Errors Only Mode", "Filters the event stream to show only Warnings, Errors, and Critical system incidents."),
        "uk": ("Режим Тільки Помилки", "Фільтрація стрічки подій: відображення виключно попереджень, помилок та критичних інцидентів."),
        "he": ("מצב שגיאות בלבד", "סינון זרם האירועים: הצגת אזהרות, שגיאות ותקלות מערכת קריטיות בלבד.")
    },
    "mode-raw": {
        "en": ("Raw Data Mode", "Unfiltered raw telemetry events and native Windows event log records."),
        "uk": ("Режим Сирих Даних", "Нефільтровані сирі дані телеметрії та нативні записи системних журналів Windows."),
        "he": ("מצב נתונים גולמיים", "אירועי טלמטריה גולמיים ללא סינון ורשומות יומן אירועים מקוריות של Windows.")
    },
    "sum-power": {
        "en": ("Power Failures", "Incidents related to improper shutdowns, kernel power loss (Event 41), and sleep wake failures."),
        "uk": ("Збої Живлення", "Інциденти некоректного вимкнення, втрати живлення ядра (Event 41) та збоїв переходу в сплячий режим."),
        "he": ("תקלות צריכת חשמל", "תקריות הקשורות לכיבוי בלתי תקין, אובדן חשמל ליבתי (Event 41) וכשלי התעוררות משינה.")
    },
    "sum-bsod": {
        "en": ("BSOD Crashes", "Blue Screen of Death crash reports, bugcheck codes, and kernel minidump analysis."),
        "uk": ("Аварії BSOD", "Звіти про сині екрани смерті (BSOD), коди перевірки помилок ядра (Bugcheck) та аналіз мінідампів."),
        "he": ("קריסות מסך כחול (BSOD)", "דוחות קריסה של מסך כחול (BSOD), קודי שגיאת ליבה (Bugcheck) וניתוח קבצי Minidump.")
    },
    "sum-drivers": {
        "en": ("Driver Faults", "Hardware device driver timeout incidents, initialization faults, and peripheral errors."),
        "uk": ("Помилки Драйверів", "Інциденти тайм-аутів драйверів пристроїв, збої ініціалізації та помилки периферії."),
        "he": ("שגיאות דרייברים", "תקריות פקיעת זמן של מנהלי התקנים, כשלי אתחול חומרה ושגיאות התקנים היקפיים.")
    },
    "sum-suspicious": {
        "en": ("Suspicious Anomalies", "Anomalous process executions, unexpected service registrations, and unusual audit events."),
        "uk": ("Підозрілі Аномалії", "Аномальні запуски процесів, підозрілі реєстрації служб та нетипові події безпеки."),
        "he": ("אנומליות חשודות", "הפעלות תהליכים חריגות, רישומי שירותים בלתי צפויים ואירועי ביקורת לא שגרתיים.")
    },
    "slc-scan": {
        "en": ("Run Diagnostics Scan", "Triggers comprehensive analysis across system event logs, crash dumps, and hardware telemetry."),
        "uk": ("Запустити Діагностику", "Запуск комплексного аналізу системних журналів, аварійних дампів та апаратної телеметрії."),
        "he": ("הפעלת סריקת אבחון", "מפעיל ניתוח מקיף של יומני אירועים, קבצי קריסה וטלמטריית חומרה של המערכת.")
    },
    "slc-refresh": {
        "en": ("Refresh Logs", "Reloads the latest event log entries and telemetry metrics from Windows providers."),
        "uk": ("Оновити Журнали", "Перезавантаження найновіших записів журналів та метрик від провайдерів Windows."),
        "he": ("רענון יומנים", "טעינה מחדש של רשומות האירועים העדכניות ומדדי הטלמטריה של Windows.")
    },
    "sum-refresh": {
        "en": ("Refresh Metrics", "Recalculates summary failure statistics and updates health scoring indicators."),
        "uk": ("Оновити Показники", "Перерахунок зведеної статистики збоїв та актуалізація індикаторів надійності системи."),
        "he": ("רענון מדדים", "מחשב מחדש את סטטיסטיקת התקלות המרכזית ומעדכן את מדדי תקינות המערכת.")
    },
    "ask-ai": {
        "en": ("System Explanation", "Detailed contextual explanation of the selected diagnostic entry and its system impact."),
        "uk": ("Пояснення Системи", "Детальне контекстне пояснення обраного діагностичного запису та його впливу на систему."),
        "he": ("הסבר המערכת", "הסבר הקשרי מפורט של רשומת האבחון שנבחרה והשפעתה על יציבות המערכת.")
    },
    "sum-export": {
        "en": ("Export Summary", "Exports system health digest and failure telemetry report as JSON or CSV."),
        "uk": ("Експорт Звіту", "Експорт зведеного звіту стану системи та телеметрії збоїв у форматі JSON або CSV."),
        "he": ("ייצוא דוח", "ייצוא תמצית בריאות המערכת ודוח טלמטריית תקלות כקובץ JSON או CSV.")
    },
    "throttling": {
        "en": ("Hardware Throttling", "Detection of thermal CPU throttling (PROCHOT), PL1/PL2 power constraints, and DPC/ISR latencies."),
        "uk": ("Термальний Тротлінг", "Детекція термального тротлінгу процесора (PROCHOT), обмежень живлення PL1/PL2 та затримок DPC/ISR."),
        "he": ("תרוטלינג וחום חומרה", "זיהוי תרוטלינג תרמי של המעבד (PROCHOT), מגבלות מתח PL1/PL2 ושיהויי DPC/ISR.")
    },
    "sw-inventory": {
        "en": ("Installed Software", "Catalog of all registered desktop applications, Windows Store apps, and package dependencies."),
        "uk": ("Встановлене ПЗ", "Каталог усіх зареєстрованих класичних програм, додатків Windows Store та залежностей."),
        "he": ("תוכנות מותקנות", "קטלוג של כל יישומי המחשב הרשומים, אפליקציות Windows Store ותלויות החבילות.")
    },
    "sw-packages": {
        "en": ("Package Managers", "Integrated management for Winget, MSI installers, and community package repositories."),
        "uk": ("Пакетні Менеджери", "Інтегроване керування через Winget, інсталятори MSI та репозиторії пакетів."),
        "he": ("מנהלי חבילות", "ניהול משולב עבור מנהל החבילות Winget, קובצי התקנה של MSI ומאגרי תוכנה.")
    },
    "sw-dormant": {
        "en": ("Dormant Software", "Detects rarely launched and dormant applications based on UserAssist telemetry to reclaim disk space."),
        "uk": ("Невикористовуване ПЗ", "Виявлення рідко використовуваних програм на основі телеметрії UserAssist для звільнення диска."),
        "he": ("תוכנות רדומות", "זיהוי יישומים שלא הופעלו זמן רב על בסיס טלמטריית UserAssist לפינוי שטח אחסון.")
    },
    "sw-transparency": {
        "en": ("Software Transparency", "Deep analysis of application files, publisher certificates, embedded drivers, and autostart tasks."),
        "uk": ("Прозорість ПЗ", "Глибокий аналіз файлової структури, сертифікатів видавця, драйверів та завдань автозапуску програми."),
        "he": ("שקיפות תוכנה", "ניתוח מעמיק של קבצי תוכנה, תעודות חתימה של מפתחים, דרייברים מוטמעים ומשימות רקע.")
    },
    "sw-heavy": {
        "en": ("Heavy Applications", "Identifies programs with oversized disk footprints, extensive cache trees, or large memory working sets."),
        "uk": ("Тяжкі Програми", "Виявлення програм із найбільшим обсягом зайнятого дискового простору та споживанням пам'яті."),
        "he": ("תוכנות כבדות", "זיהוי יישומים התופסים שטח דיסק עצום, עצי מטמון כבדים או צריכת זיכרון חריגה.")
    },
    "sw-sockets": {
        "en": ("Network Sockets", "Audits background network listeners, outbound connections, and listening ports owned by software."),
        "uk": ("Мережеві Сокети", "Аудит фонової мережевої активності, відкритих портів та вихідних з'єднань програм."),
        "he": ("חיבורי רשת (Sockets)", "ביקורת על תהליכים המאזינים ברשת, חיבורים יוצאים ופורטים פתוחים של תוכנות.")
    },
    "sw-winget": {
        "en": ("Windows Package Manager (Winget)", "Official CLI and repository for silent application installations, upgrades, and uninstalls."),
        "uk": ("Winget Менеджер", "Офіційний менеджер пакетів Windows для автоматичного встановлення, оновлення та видалення програм."),
        "he": ("מנהל החבילות Winget", "כלי ומאגר רשמי של Windows להתקנה שקטה, שדרוג והסרה של יישומים.")
    },
    "sw-msi": {
        "en": ("MSI Packages", "Inspects Windows Installer database packages, patch states, and registered GUID components."),
        "uk": ("Пакети MSI", "Перевірка пакетів Windows Installer, стану виправлень та зареєстрованих компонентів GUID."),
        "he": ("חבילות MSI", "בדיקת חבילות Windows Installer, מצב עדכוני אבטחה ורכיבי GUID רשומים במערכת.")
    },
    "sw-store": {
        "en": ("Microsoft Store Apps", "Management of Appx and MSIX packaged universal Windows platform applications."),
        "uk": ("Додатки Microsoft Store", "Керування універсальними додатками Windows у пакетах Appx та MSIX."),
        "he": ("אפליקציות Microsoft Store", "ניהול אפליקציות אוניברסליות של Windows הארוזות בתקן Appx ו-MSIX.")
    },
    "sw-ninite": {
        "en": ("Ninite Automation", "Automated multi-package installer and updater for essential third-party utilities."),
        "uk": ("Автоматизація Ninite", "Автоматизоване пакетне оновлення та встановлення популярних безкоштовних утиліт."),
        "he": ("אוטומציית Ninite", "התקנה ושדרוג אוטומטיים של חבילות תוכנה חיוניות ללא התערבות ידנית.")
    },
    "sw-scan-trigger": {
        "en": ("Scan Software Inventory", "Scans registry hives, uninstall keys, and file system roots to refresh application list."),
        "uk": ("Сканувати Інвентар ПЗ", "Сканування гілок реєстру та файлової системи для повного оновлення списку встановленого ПЗ."),
        "he": ("סריקת מלאי תוכנה", "סורק את הרישום (Registry) ומערכת הקבצים לרענון רשימת התוכנות המותקנות.")
    },
    "sw-scan-modes": {
        "en": ("Scanning Depth", "Switch between fast registry enumeration and thorough disk-level heuristic detection."),
        "uk": ("Глибина Сканування", "Перемикання між швидким опитуванням реєстру та глибоким евристичним пошуком на дисках."),
        "he": ("עומק סריקה", "מעבר בין סריקת רישום מהירה לבין בדיקה יסודית ברמת מערכת הקבצים.")
    },
    "sw-filter-dormant": {
        "en": ("Filter Dormant Apps", "Displays only programs that have not been launched within the last 60+ days."),
        "uk": ("Фільтр Невикористовуваного", "Показує лише програми, які не запускалися понад 60 днів."),
        "he": ("סינון תוכנות רדומות", "מציג אך ורק יישומים שלא הופעלו במהלך 60 הימים האחרונים.")
    },
    "sw-filter-orphan": {
        "en": ("Filter Orphaned Leftovers", "Shows detected residual files, empty folders, and orphaned registry keys from uninstalled software."),
        "uk": ("Фільтр Залишкових Файлів", "Відображає виявлені залишкові файли, порожні папки та застарілі ключі реєстру видаленого ПЗ."),
        "he": ("סינון שיירי תוכנה", "מציג קבצים שנותרו, תיקיות ריקות ומפתחות רישום מיותרים של תוכנות שהוסרו.")
    },
    "sw-filter-store": {
        "en": ("Filter Store Apps", "Isolates modern UWP/MSIX applications delivered through the Microsoft Store."),
        "uk": ("Фільтр Store Додатків", "Фільтрація сучасних додатків UWP/MSIX, завантажених через Microsoft Store."),
        "he": ("סינון אפליקציות Store", "מבודד יישומי UWP/MSIX מודרניים שהותקנו דרך חנות Microsoft Store.")
    },
    "sw-refresh-heavy": {
        "en": ("Recalculate Disk Usage", "Updates directory size calculations to pinpoint space-consuming software suites."),
        "uk": ("Перерахувати Обсяг Диска", "Оновлює розрахунок розмірів папок для виявлення найбільш громіздких програм."),
        "he": ("חישוב שטח דיסק מחדש", "מעדכן את חישוב גודל התיקיות לזיהוי התוכנות התופסות את מרב שטח האחסון.")
    },
    "sw-refresh-sockets": {
        "en": ("Refresh Socket Table", "Polls active network ports and open sockets currently bound by software components."),
        "uk": ("Оновити Мережеві Сокети", "Опитування відкритих мережевих портів та активних сокетів, зайнятих програмами."),
        "he": ("רענון חיבורי רשת", "בודק את הפורטים והחיבורים הפעילים ברשת המשויכים לתוכנות המותקנות.")
    },
    "sw-orphans": {
        "en": ("Orphaned Software Files", "Locates leftover files, empty directory trees, and dangling registry paths after broken uninstalls."),
        "uk": ("Остаточні файли ПЗ", "Виявлення залишкових файлів, порожніх папок у Program Files та застарілих ключів реєстру."),
        "he": ("שאריות תוכנה יתומות", "איתור קבצים שנותרו, תיקיות ריקות ונתיבי רישום שבורים לאחר הסרת תוכנות.")
    },
    "sw-startup": {
        "en": ("Startup Applications", "Audits run keys, startup folders, and scheduled tasks launched during Windows boot."),
        "uk": ("Автозавантаження програм", "Аналіз програм, служб та планувальника завдань, що запускаються під час старту Windows."),
        "he": ("תוכניות בהפעלה אוטומטית", "ביקורת על מפתחות הפעלה ברישום, תיקיות הפעלה ומשימות מתוזמנות בעליית Windows.")
    },
    "winadmin-users": {
        "en": ("User Accounts", "Local Windows user accounts management, password policies, and account state inspection."),
        "uk": ("Облікові Записи", "Керування локальними користувачами Windows, політиками паролів та станом акаунтів."),
        "he": ("חשבונות משתמשים", "ניהול חשבונות משתמש מקומיים ב-Windows, מדיניות סיסמאות ובדיקת מצב חשבונות.")
    },
    "winadmin-groups": {
        "en": ("Security Groups", "Administration of local security groups (Administrators, Users, Remote Desktop Users, etc.)."),
        "uk": ("Групи Безпеки", "Керування локальними групами безпеки (Administrators, Users, Remote Desktop Users тощо)."),
        "he": ("קבוצות אבטחה", "ניהול קבוצות אבטחה מקומיות (Administrators, Users, Remote Desktop Users ועוד).")
    },
    "winadmin-events": {
        "en": ("Security Event Log", "Audit logs tracking user authentication (Event 4624/4625), privilege escalation, and account changes."),
        "uk": ("Журнал Аудиту Безпеки", "Журнали реєстрації автентифікації користувачів (4624/4625), підвищення привілеїв та змін акаунтів."),
        "he": ("יומן אירועי אבטחה", "יומני ביקורת העוקבים אחר התחברות משתמשים (אירועים 4624/4625), העלאת הרשאות ושינויי חשבון.")
    },
    "winadmin-security": {
        "en": ("System Hardening", "Inspection of local security policies, UAC levels, LSA protection, and credential guard status."),
        "uk": ("Політики Безпеки", "Перевірка локальних політик безпеки, рівня UAC, захисту LSA та ізоляції облікових даних."),
        "he": ("הקשחת אבטחת מערכת", "בדיקת מדיניות אבטחה מקומית, רמת בקרת חשבון משתמש (UAC), הגנת LSA ובידוד אישורים.")
    },
    "winadmin-pid": {
        "en": ("PID Security Inspector", "Maps running process identifiers (PID) to owning user security tokens, SIDs, and privilege sets."),
        "uk": ("Інспектор PID", "Зіставлення ідентифікаторів процесів (PID) із токенами безпеки користувача, SID та привілеями."),
        "he": ("מפקח תהליכים לפי PID", "ממפה מזהי תהליכים (PID) לטוקנים מאובטחים של המשתמש, מזהי SID וסט הרשאות.")
    },
    "winadmin-catalog": {
        "en": ("System Catalog", "Windows administrative tools and command reference for maintenance and troubleshooting."),
        "uk": ("Каталог Системи", "Довідник адміністративних інструментів та системних команд Windows для обслуговування."),
        "he": ("קטלוג כלי מערכת", "מדריך כלי ניהול ופקודות מערכת של Windows לתחזוקה ואיתור תקלות.")
    },
    "winadmin-acl": {
        "en": ("Access Control Lists (ACL)", "Permissions editor for files, folders, registry keys, and system securable objects."),
        "uk": ("Керування Доступом (ACL)", "Редактор прав доступу до файлів, папок, гілок реєстру та захищених об'єктів ОС."),
        "he": ("רשימות בקרת גישה (ACL)", "עורך הרשאות עבור קבצים, תיקיות, מפתחות רישום ואובייקטים מאובטחים במערכת.")
    },
    "winadmin-refresh": {
        "en": ("Refresh User Data", "Updates list of local user accounts, active sessions, and group memberships."),
        "uk": ("Оновити Дані Користувачів", "Оновлення списку локальних акаунтів, активних сесій та членства в групах."),
        "he": ("רענון נתוני משתמשים", "מעדכן את רשימת חשבונות המשתמש המקומיים, הפעלות פעילות וחברות בקבוצות.")
    },
    "winadmin-create-user": {
        "en": ("Create Local User", "Opens wizard to create a new local user account with designated privileges and password."),
        "uk": ("Створити Користувача", "Відкриває майстер створення нового локального облікового запису з паролем і правами."),
        "he": ("יצירת משתמש מקומי", "פותח אשף ליצירת חשבון משתמש מקומי חדש עם הרשאות מוגדרות וסיסמה.")
    },
    "winadmin-privacy-radar": {
        "en": ("Privacy Radar", "Audits Windows telemetry transmission, diagnostic data levels, and background data collectors."),
        "uk": ("Радар Приватності", "Аудит передавання телеметрії Windows, рівня діагностичних даних та фонових збирачів."),
        "he": ("רדאר פרטיות", "ביקורת על שידור טלמטריה של Windows, רמות נתוני אבחון ואיסוף מידע ברקע.")
    },
    "winadmin-backup": {
        "en": ("System Backup", "Volume Shadow Copy Service (VSS) status, system restore points, and backup integrity."),
        "uk": ("Резервне Копіювання", "Стан служби тіньового копіювання (VSS), точок відновлення та цілісності бекапів."),
        "he": ("גיבוי ושחזור מערכת", "מצב שירות עותקי צל (VSS), נקודות שחזור מערכת ותקינות גיבויים קיימים.")
    },
    "winadmin-audit-admins": {
        "en": ("Audit Administrators", "Identifies all accounts holding local administrative privileges across the system."),
        "uk": ("Аудит Адміністраторів", "Перевірка всіх облікових записів із правами локального адміністратора."),
        "he": ("ביקורת מנהלי מערכת", "מזהה את כל החשבונות המחזיקים בהרשאות ניהול מקומיות במחשב.")
    },
    "winadmin-audit-service": {
        "en": ("Audit Service Logons", "Audits user accounts authorized for 'Log on as a service' rights (SeServiceLogonRight)."),
        "uk": ("Аудит Службового Входу", "Перевірка облікових записів із правом входу як служба (SeServiceLogonRight)."),
        "he": ("ביקורת כניסה כשירות", "ביקורת על חשבונות בעלי הרשאת 'כניסה כשירות' (SeServiceLogonRight).")
    },
    "winadmin-audit-rdp": {
        "en": ("Audit RDP Access", "Inspects users and groups permitted for Remote Desktop Protocol remote sessions."),
        "uk": ("Аудит Доступу RDP", "Перевірка користувачів та груп із дозволом на підключення через віддалений робочий стіл."),
        "he": ("ביקורת גישת שולחן עבודה מרוחק", "בודק משתמשים וקבוצות בעלי הרשאה להתחברות מרחוק באמצעות פרוטוקול RDP.")
    },
    "winadmin-audit-orphaned": {
        "en": ("Audit Orphaned Profiles", "Detects user profiles on disk that are no longer bound to any active user account."),
        "uk": ("Аудит Залишкових Профілів", "Виявлення каталогів профілів користувачів на диску, які більше не мають чинного акаунту."),
        "he": ("ביקורת פרופילים יתומים", "מזהה תיקיות פרופיל משתמש בדיסק שאינן מקושרות עוד לאף חשבון פעיל.")
    },
    "winadmin-acl-takeown": {
        "en": ("Take Ownership", "Assigns ownership of the selected file, folder, or registry key to Administrators."),
        "uk": ("Зміна Власника", "Призначення групи Administrators власником обраного файлу, папки або ключа реєстру."),
        "he": ("קבלת בעלות", "העברת הבעלות על הקובץ, התיקייה או מפתח הרישום שנבחרו לקבוצת מנהלי המערכת.")
    },
    "winadmin-acl-reset": {
        "en": ("Reset Default Permissions", "Restores standard inherited Windows permissions on the target system object."),
        "uk": ("Скинути Права за Замовчуванням", "Відновлення стандартних успадкованих прав доступу Windows на цільовому об'єкті."),
        "he": ("איפוס הרשאות ברירת מחדל", "משחזר הרשאות ירושה תקניות של Windows על אובייקט המערכת הנבחר.")
    },
    "winadmin-acl-backup": {
        "en": ("Backup Security ACL", "Exports current access control list descriptors to a backup file before modification."),
        "uk": ("Резервна Копія ACL", "Збереження поточного дескриптора безпеки та списку прав у бекап перед змінами."),
        "he": ("גיבוי רשימת ACL", "מייצא את הרשאות הגישה הנוכחיות לקובץ גיבוי מאובטח לפני ביצוע שינויים.")
    },
    "winadmin-acl-rollback": {
        "en": ("Rollback Security ACL", "Restores previously saved security descriptors and permissions on the object."),
        "uk": ("Відкотити Права ACL", "Відновлення раніше збережених дескрипторів безпеки та прав доступу на об'єкті."),
        "he": ("שחזור רשימת ACL", "משחזר הרשאות גישה שנשמרו בעבר על גבי אובייקט המערכת.")
    },
    "winadmin-acl-inspect": {
        "en": ("Inspect ACL Details", "Displays detailed discretionary access control list (DACL) ACE entries for the object."),
        "uk": ("Детальний Перегляд ACL", "Відображення детальних записів керування доступом (ACE/DACL) для обраного об'єкта."),
        "he": ("בדיקת פרטי הרשאות ACL", "מציג רשומות בקרת גישה מפורטות (DACL / ACE) עבור האובייקט הנבחר.")
    },
    "winadmin-acl-grant": {
        "en": ("Grant Access Rights", "Grants specified read, write, or full control permissions to a user or group."),
        "uk": ("Надати Права Доступу", "Надання зазначених прав читання, запису або повного доступу користувачеві чи групі."),
        "he": ("הענקת הרשאות גישה", "מעניק הרשאות קריאה, כתיבה או שליטה מלאה למשתמש או לקבוצה מוגדרת.")
    },
    "winadmin-filter-hidden": {
        "en": ("Filter Hidden Accounts", "Shows built-in and disabled system accounts (DefaultAccount, Guest, WDAGUtilityAccount)."),
        "uk": ("Фільтр Прихованих Акаунтів", "Відображення вбудованих та вимкнених облікових записів системи."),
        "he": ("סינון חשבונות מוסתרים", "מציג חשבונות מערכת מובנים ומושבתים (DefaultAccount, Guest ועוד).")
    },
    "winadmin-filter-admins": {
        "en": ("Filter Administrators", "Filters list to display only accounts belonging to the local Administrators group."),
        "uk": ("Фільтр Адміністраторів", "Фільтрація списку: показ виключно акаунтів, що входять до групи Administrators."),
        "he": ("סינון מנהלי מערכת", "מסנן את הרשימה להצגת חשבונות השייכים לקבוצת Administrators בלבד.")
    },
    "proc-engine-status": {
        "en": ("Inspector Engine Status", "Current telemetry engine polling rate and background worker health status."),
        "uk": ("Статус Рушія Інспектора", "Поточна частота опитування телеметрії та стан фонового сервісу інспектора."),
        "he": ("סטטוס מנוע הבדיקה", "קצב דגימת טלמטריה נוכחי ומצב תקינות תהליכי הרקע של מפקח המערכת.")
    },
    "proc-global-refresh": {
        "en": ("Refresh All Processes", "Refreshes process table, tree hierarchy, memory counters, and open file handles."),
        "uk": ("Оновити Всі Процеси", "Оновлення таблиці процесів, ієрархії дерев, лічильників пам'яті та дескрипторів."),
        "he": ("רענון כלל התהליכים", "מרענן את טבלת התהליכים, היררכיית העצים, מונים של זיכרון וידיות קבצים פתוחות.")
    },
    "proc-subtab-manager": {
        "en": ("Process Manager Tab", "Task Manager view organizing Apps, Background processes, and Windows system trees."),
        "uk": ("Диспетчер Процесів", "Вкладка диспетчера задач із групуванням програм (Apps), фонових та системних процесів Windows."),
        "he": ("לשונית מנהל המשימות", "תצוגת מנהל משימות המארגנת יישומים, תהליכי רקע ועצי תהליכי מערכת של Windows.")
    },
    "proc-subtab-top": {
        "en": ("Top CPU / RAM Stream", "Real-time leaderboard of processes consuming the highest CPU and memory resources."),
        "uk": ("Топ Процесів Хоста", "Рейтинг процесів у реальному часі за найбільшим споживанням процесора та оперативної пам'яті."),
        "he": ("זרם תהליכים מובילים", "דירוג בזמן אמת של התהליכים הצורכים את כמות המשאבים הגבוהה ביותר (מעבד וזיכרון).")
    },
    "proc-subtab-net": {
        "en": ("Network Activity Tab", "Live tracking of active TCP/UDP connections, listening sockets, and data transfer rates."),
        "uk": ("Сетева Активність", "Відстеження активних з'єднань TCP/UDP, прослуховуваних портів та швидкості передавання даних."),
        "he": ("לשונית פעילות רשת", "מעקב חי אחר חיבורי TCP/UDP פעילים, פורטים מאזינים וקצבי העברת נתונים של תהליכים.")
    },
    "proc-subtab-files": {
        "en": ("File Operations Stream", "Real-time stream of file creations, modifications, and deletions via ReadDirectoryChangesW."),
        "uk": ("Моніторинг Файлів", "Стрічка створення, зміни та видалення файлів на диску в реальному часі через ReadDirectoryChangesW."),
        "he": ("זרם פעולות קבצים", "פיד בזמן אמת של יצירת קבצים, שינויים ומחיקות בדיסק באמצעות ReadDirectoryChangesW.")
    },
    "proc-subtab-leaks": {
        "en": ("Resource Leak Hunter", "Identifies processes with ballooning handles, GDI/USER object exhaustion, and memory leaks."),
        "uk": ("Аудит Витоків Ресурсів", "Виявлення процесів із надмірним накопиченням дескрипторів, об'єктів GDI/USER та витоками пам'яті."),
        "he": ("איתור דליפות משאבים", "זיהוי תהליכים בעלי הצטברות חריגה של ידיות (Handles), אובייקטי GDI/USER ודליפות זיכרון.")
    },
    "pm-card-apps": {
        "en": ("Interactive Applications", "Filter viewing desktop and foreground applications with graphical window interfaces."),
        "uk": ("Інтерактивні Програми", "Фільтр відображення користувацьких програм із графічними вікнами інтерфейсу."),
        "he": ("יישומים אינטראקטיביים", "סינון להצגת יישומי שולחן עבודה בעלי ממשק חלונות גרפי הנמצאים בשימוש.")
    },
    "pm-card-bg": {
        "en": ("Background Processes", "Filter viewing background worker processes and daemon utilities without user interfaces."),
        "uk": ("Фонові Процеси", "Фільтр відображення фонових службових процесів без активного графічного інтерфейсу."),
        "he": ("תהליכי רקע", "סינון להצגת תהליכי שירות ותוכניות עזר ברקע הפועלות ללא ממשק משתמש.")
    },
    "pm-card-win": {
        "en": ("Windows System Processes", "Filter isolating essential core Windows operating system services and drivers."),
        "uk": ("Процеси Windows", "Фільтр відображення критичних системних процесів та служб операційної системи Windows."),
        "he": ("תהליכי מערכת Windows", "סינון מבודד להצגת שירותי ליבה ותהליכים חיוניים של מערכת ההפעלה Windows.")
    },
    "pm-card-all": {
        "en": ("All Processes", "Consolidated view of all running processes across all session boundaries and users."),
        "uk": ("Усі Процеси", "Зведене відображення абсолютно всіх активних процесів у всіх сесіях користувачів."),
        "he": ("כלל התהליכים", "תצוגה כוללת של כל התהליכים הפועלים במערכת בכל ההפעלות והמשתמשים.")
    },
    "pm-refresh": {
        "en": ("Refresh Process Tree", "Rebuilds process tree hierarchy and recalculates aggregate group metrics."),
        "uk": ("Оновити Дерево Процесів", "Перебудова ієрархії дерева процесів та перерахунок сумарних метрик груп."),
        "he": ("רענון עץ התהליכים", "בונה מחדש את היררכיית עץ התהליכים ומחשב מחדש את מדדי הקבוצות המצטברים.")
    },
    "pm-category-filters": {
        "en": ("Category Switcher", "Quick filter toggles between Apps, Background, and Windows process categories."),
        "uk": ("Перемикач Категорій", "Швидке перемикання між категоріями програм, фонових та системних процесів."),
        "he": ("בורר קטגוריות", "מעבר מהיר בין קטגוריות יישומים, תהליכי רקע ותהליכי מערכת של Windows.")
    },
    "pm-toggle-expand": {
        "en": ("Expand All Trees", "Expands or collapses all parent process groups and subprocess hierarchies."),
        "uk": ("Розгорнути Всі Дерева", "Розгортає або згортає всі батьківські групи та ієрархії підпроцесів."),
        "he": ("הרחבת כל העצים", "מרחיב או מכווץ את כל קבוצות התהליכים הראשיות והיררכיות תהליכי המשנה.")
    },
    "pm-ai-modal": {
        "en": ("Process Passport", "Inspects runtime security, digital signatures, memory map, and telemetry for this process."),
        "uk": ("Паспорт Процесу", "Перевірка безпеки виконання, цифрового підпису, пам'яті та телеметрії процесу."),
        "he": ("דרכון תהליך", "בדיקת אבטחה, חתימה דיגיטלית, מפת זיכרון וטלמטריה של התהליך הנבחר.")
    },
    "pm-investigate-ps": {
        "en": ("PowerShell Inspection", "Extracts active command line parameters, script blocks, and parent process trees for inspection."),
        "uk": ("Аудит PowerShell", "Отримання параметрів командного рядка, блоків скриптів та ієрархії запуску процесу."),
        "he": ("חקירת פקודות PowerShell", "חילוץ פרמטרי שורת פקודה פעילים, בלוקי סקריפטים ועצי תהליך אב לבדיקה.")
    },
    "pm-prompt-settings": {
        "en": ("Inspector Settings", "Configure thresholds for high CPU, excessive memory, and process anomaly alerting."),
        "uk": ("Налаштування Інспектора", "Конфігурація порогів високого навантаження CPU, пам'яті та сповіщень про аномалії."),
        "he": ("הגדרות מפקח", "הגדרת ספי התרעה לעומס מעבד גבוה, שימוש מופרז בזיכרון ואנומליות של תהליכים.")
    },
    "proc-top-pause": {
        "en": ("Pause Stream", "Freezes top process stream to allow inspection of transient process spikes."),
        "uk": ("Пауза Потоку", "Призупиняє оновлення топу процесів для спокійного аналізу короткочасних сплесків навантаження."),
        "he": ("השהיית זרם", "מקפיא את זרם התהליכים המובילים כדי לאפשר בדיקה של עליות עומס קצרות.")
    },
    "proc-top-refresh": {
        "en": ("Refresh Top Stream", "Immediate request to pull current top CPU and RAM consuming processes."),
        "uk": ("Оновити Топ Процесів", "Негайне опитування поточних процесів із найвищим споживанням ресурсів."),
        "he": ("רענון תהליכים מובילים", "בקשה מיידית לשליפת התהליכים בעלי צריכת המשאבים הגבוהה ביותר כעת.")
    },
    "proc-top-ai-modal": {
        "en": ("Process Telemetry Passport", "Detailed process passport with CPU, RAM, OS handles, sockets, and file operations telemetry."),
        "uk": ("Паспорт Процесу", "Детальний паспорт процесу з метриками CPU, RAM, дескрипторів ОС, сокетів та файлової активності."),
        "he": ("דרכון טלמטריה של תהליך", "דרכון תהליך מפורט הכולל מדדי מעבד, זיכרון, ידיות מערכת הפעלה, סוקטים ופעילות קבצים.")
    },
    "proc-top-prompt-settings": {
        "en": ("Process Rules Configuration", "Configures process inspection rules, thresholds for handle leaks, and inspector profiles."),
        "uk": ("Налаштування Правил Процесів", "Конфігурація правил аудиту процесів, порогів витоків дескрипторів та профілів інспектора."),
        "he": ("הגדרת כללי תהליכים", "הגדרת כללי ביקורת תהליכים, ספי התרעה לדליפות משאבים ופרופילי בדיקה.")
    },
    "proc-net-filter-internet": {
        "en": ("Filter Internet Connections", "Displays only external remote internet sockets, filtering out local loopback (127.0.0.1)."),
        "uk": ("Фільтр Інтернет-З'єднань", "Відображає лише зовнішні інтернет-з'єднання, приховуючи локальний loopback (127.0.0.1)."),
        "he": ("סינון חיבורי אינטרנט", "מציג אך ורק חיבורי אינטרנט חיצוניים, ומסנן תקשורת מקומית פנימית (127.0.0.1).")
    },
    "proc-net-pause": {
        "en": ("Pause Network Monitoring", "Freezes network connections table to analyze established sockets."),
        "uk": ("Пауза Моніторингу Мережі", "Призупиняє оновлення таблиці з'єднань для аналізу встановлених сокетів."),
        "he": ("השהיית ניטור רשת", "מקפיא את טבלת חיבורי הרשת כדי לאפשר ניתוח של חיבורים קיימים.")
    },
    "proc-net-refresh": {
        "en": ("Refresh Network Connections", "Polls active network connections, socket states, and per-process transfer rates."),
        "uk": ("Оновити Мережеві З'єднання", "Опитування активних мережевих з'єднань, стану сокетів та швидкості передавання."),
        "he": ("רענון חיבורי רשת", "דוגם חיבורי רשת פעילים, מצבי סוקטים וקצבי העברת נתונים לפי תהליך.")
    },
    "proc-watch-badge": {
        "en": ("Monitored Directory", "Target filesystem directory path currently observed for file modification events."),
        "uk": ("Контрольована Папка", "Шлях до каталогу файлової системи, за яким ведеться спостереження змін файлів."),
        "he": ("תיקייה מנוטרת", "נתיב תיקיית מערכת הקבצים הנמצאת כעת תחת מעקב אחר שינויים ויצירת קבצים.")
    },
    "proc-watch-exclusions": {
        "en": ("Watcher Exclusions", "Configure ignored directories and file extensions (e.g., *.log, *.tmp) to suppress noise."),
        "uk": ("Виключення Монітора", "Налаштування папок та розширень (наприклад *.log, *.tmp), що ігноруються монітором."),
        "he": ("חריגות ניטור קבצים", "הגדרת תיקיות וסיומות קבצים המוחרגות ממעקב (כגון log.*, tmp.*) למניעת עומס נתונים.")
    },
    "proc-watch-change-dir": {
        "en": ("Change Watch Target", "Selects a different directory path on any local drive for real-time filesystem tracking."),
        "uk": ("Змінити Папку Спостереження", "Вибір іншого каталогу на будь-якому локальному диску для моніторингу файлів."),
        "he": ("שינוי תיקיית יעד לניטור", "בחירת נתיב תיקייה אחר בכל כונן מקומי למעקב אחר שינויי קבצים בזמן אמת.")
    },
    "proc-watch-refresh": {
        "en": ("Clear & Refresh Events", "Clears event history buffer and requests recent filesystem events from Windows."),
        "uk": ("Очистити та Оновити", "Очищення буфера журналу та опитування останніх подій файлової системи Windows."),
        "he": ("ניקוי ורענון אירועים", "מנקה את זיכרון האירועים ושולף אירועי מערכת קבצים אחרונים מ-Windows.")
    },
    "diag-leaks-total": {
        "en": ("Monitored Processes", "Total count of active Windows processes tracked for resource leaks and handle accumulation."),
        "uk": ("Всього Процесів", "Загальна кількість процесів Windows, що аналізуються на витоки ресурсів та дескрипторів."),
        "he": ("תהליכים מנוטרים", "המספר הכולל של תהליכי Windows הנמצאים תחת מעקב לאיתור דליפות משאבים.")
    },
    "diag-leaks-suspicious": {
        "en": ("Suspicious Leak Anomalies", "Processes with handle or GDI growth rates exceeding normal operating safety margins."),
        "uk": ("Підозрілі Аномалії Витоків", "Процеси з темпом росту дескрипторів або GDI, що перевищує норми безпеки."),
        "he": ("אנומליות דליפה חשודות", "תהליכים עם קצב גידול ידיות או אובייקטי GDI החורג מסף הבטיחות התקין.")
    },
    "diag-leaks-handles": {
        "en": ("Peak Handle Consumption", "Process holding the highest count of open operating system kernel object handles."),
        "uk": ("Пік Дескрипторів ОС", "Процес із найбільшою кількістю відкритих дескрипторів об'єктів ядра ОС."),
        "he": ("שיא שימוש בידיות (Handles)", "התהליך המחזיק במספר הגבוה ביותר של ידיות אובייקטי ליבה פתוחות.")
    },
    "diag-leaks-gdi": {
        "en": ("Peak GDI Object Usage", "Process consuming the most GUI drawing resources against the 10,000 Windows limit."),
        "uk": ("Пік Об'єктів GDI", "Процес із найбільшою кількістю графічних об'єктів GDI відносно ліміту 10 000 у Windows."),
        "he": ("שיא אובייקטי גרפיקה (GDI)", "התהליך הצורך את הכמות הגבוהה ביותר של אובייקטי GDI מול מגבלת 10,000 ב-Windows.")
    },
    "diag-leaks-filters": {
        "en": ("Leak Severity Filter", "Filter process table by suspicious leak scores, excessive handles, or high GDI usage."),
        "uk": ("Фільтри Витоків Ресурсів", "Фільтрація таблиці процесів за ризиком витоку, надмірними дескрипторами чи GDI."),
        "he": ("סינון חומרת דליפות", "סינון טבלת תהליכים לפי רמת סיכון לדליפה, מספר ידיות גבוה או שימוש חריג ב-GDI.")
    },
    "diag-leaks-refresh": {
        "en": ("Audit Resource Leaks", "Performs real-time audit of process handles, GDI/USER objects, and page fault rates."),
        "uk": ("Аудит Витоків Ресурсів", "Запуск перевірки дескрипторів, графічних об'єктів GDI/USER та помилок сторінок пам'яті."),
        "he": ("ביקורת דליפות משאבים", "מבצע בדיקה בזמן אמת של ידיות תהליכים, אובייקטי GDI/USER וקצב שגיאות דפדוף בזיכרון.")
    },
    # Системные процессы Windows
    "dwm.exe": {
        "en": ("Desktop Window Manager (DWM)", "Compositing window manager in Windows rendering visual window effects, hardware acceleration, and display composition."),
        "uk": ("Диспетчер вікон стільниці (DWM)", "Композитний менеджер вікон Windows, що відповідає за візуальні ефекти, апаратне прискорення та відтворення зображення."),
        "he": ("מנהל חלונות שולחן העבודה (DWM)", "מנהל חלונות של Windows האחראי על רינדור אפקטים חזותיים, האצת חומרה והרכבת תצוגה.")
    },
    "explorer.exe": {
        "en": ("Windows Explorer", "User shell providing taskbar, desktop, start menu, notification area, and file manager navigation."),
        "uk": ("Провідник Windows", "Оболонка користувача Windows: панель задач, стільниця, меню 'Пуск', область сповіщень та файловий менеджер."),
        "he": ("סייר Windows (Explorer)", "מעטפת המשתמש המספקת את שורת המשימות, שולחן העבודה, תפריט ההתחלה וניהול קבצים.")
    },
    "svchost.exe": {
        "en": ("Host Process for Windows Services", "Shared service host running DLL-based background services grouped by security context and isolation level."),
        "uk": ("Хост-процес служб Windows (svchost)", "Системний процес, що виконує фонові служби Windows із бібліотек DLL, згруповані за рівнем ізоляції."),
        "he": ("תהליך מארח לשירותי Windows (svchost)", "תהליך מערכת המארח שירותי רקע מבוססי DLL המחולקים לפי רמות בידוד והרשאות אבטחה.")
    },
    "taskhostw.exe": {
        "en": ("Host Process for Windows Tasks", "Executes scheduled tasks, background maintenance triggers, and event telemetry scripts."),
        "uk": ("Хост завдань Windows (taskhostw)", "Виконує заплановані системні завдання, фонові тригери обслуговування та скрипти телеметрії."),
        "he": ("מארח משימות Windows (taskhostw)", "מבצע משימות מתוזמנות, פעולות תחזוקה ברקע וסקריפטים של טלמטריית אירועים.")
    },
    "lsass.exe": {
        "en": ("Local Security Authority (LSASS)", "Core Windows security process managing user authentications, credential tickets, and local security policy."),
        "uk": ("Служба безпеки LSA (lsass)", "Критичний процес безпеки Windows, що керує входом користувачів, токенами автентифікації та політиками LSA."),
        "he": ("רשות האבטחה המקומית (LSASS)", "תהליך אבטחה קריטי של Windows המנהל אימותי כניסה, אסימוני זיהוי ומדיניות אבטחה מקומית.")
    },
    "csrss.exe": {
        "en": ("Client Server Runtime (CSRSS)", "Essential Win32 subsystem component managing console windows, process shutdowns, and thread creation."),
        "uk": ("Підсистема CSRSS", "Критичний компонент підсистеми Win32, що керує консольними вікнами, створенням потоків та завершенням процесів."),
        "he": ("תת-מערכת הלקוח-שרת (CSRSS)", "רכיב תת-מערכת Win32 חיוני המנהל חלונות קונסולה, כיבוי תהליכים ויצירת תהליכונים.")
    },
    "services.exe": {
        "en": ("Service Control Manager", "Starts, stops, monitors, and administers background Windows system services and driver dependencies."),
        "uk": ("Диспетчер Керування Службами", "Керує запуском, зупинкою, моніторингом та залежностями системних служб і драйверів Windows."),
        "he": ("מנהל בקרת השירותים (SCM)", "מתניע, עוצר, מנטר ומנהל את שירותי הרקע ותלויות מנהלי ההתקנים של Windows.")
    },
    "smss.exe": {
        "en": ("Session Manager Subsystem", "First user-mode process initialized by kernel creating system environments, paging files, and sessions."),
        "uk": ("Диспетчер Сесій (smss)", "Перший процес користувацького режиму, що ініціалізує змінні середовища, файл підкачки та системні сесії."),
        "he": ("מנהל ההפעלות (SMSS)", "תהליך מצב המשתמש הראשון המופעל על ידי הליבה, יוצר את קובצי ההחלפה, סביבת המערכת והפעלות.")
    },
    "winlogon.exe": {
        "en": ("Windows Logon Application", "Handles interactive user logon, SAS secure attention sequences (Ctrl+Alt+Del), and desktop locking."),
        "uk": ("Програма Входу Windows (winlogon)", "Відповідає за безпечний вхід користувача в систему, обробку комбінації Ctrl+Alt+Del та блокування екрана."),
        "he": ("יישום הכניסה של Windows (winlogon)", "מטפל בכניסת משתמשים מאובטחת, רצף תשומת לב מאובטח (Ctrl+Alt+Del) ונעילת שולחן עבודה.")
    },
    "wininit.exe": {
        "en": ("Windows Initialization (wininit)", "Initializes background system services, creates spooler directories, and launches SCM and LSASS."),
        "uk": ("Ініціалізація Windows (wininit)", "Процес ініціалізації фонових підсистем, що запускає Диспетчер служб (SCM), LSASS та LSA."),
        "he": ("אתחול Windows (wininit)", "מאתחל שירותי מערכת ברקע, יוצר תיקיות שירות ומפעיל את מנהל השירותים (SCM) ו-LSASS.")
    },
    "powershell.exe": {
        "en": ("Windows PowerShell", "Task-based command-line shell and scripting language built on .NET for system administration."),
        "uk": ("Windows PowerShell", "Потужна командна оболонка та скриптова мова на базі .NET для автоматизації та адміністрування системи."),
        "he": ("Windows PowerShell", "מעטפת שורת פקודה ושפת סקריפטים מתקדמת המבוססת על NET. לניהול ואוטומציה של המערכת.")
    },
    "cmd.exe": {
        "en": ("Windows Command Processor", "Classic Windows command line interpreter running batch files and standard win32 console commands."),
        "uk": ("Командний Процесор Windows (cmd)", "Класичний інтерпретатор командного рядка для запуску пакетних файлів (BAT/CMD) та консольних утиліт."),
        "he": ("מעבד הפקודות של Windows (cmd)", "מפרש שורת פקודה קלאסי של Windows להפעלת קובצי אצווה (Batch) ופקודות קונסולה.")
    },
    "conhost.exe": {
        "en": ("Console Window Host", "Host process mediating I/O between command-line shells (cmd, powershell) and desktop GUI subsystem."),
        "uk": ("Хост Консольного Вікна (conhost)", "Проміжний процес, що забезпечує введення/виведення та інтерфейс між консольними утилітами та GUI."),
        "he": ("מארח חלון הקונסולה (conhost)", "תהליך מארח המתווך פעולות קלט/פלט בין שורת הפקודה (cmd, powershell) לממשק המשתמש.")
    },
    "msmpeng.exe": {
        "en": ("Antimalware Service Executable", "Core scanning engine of Microsoft Defender Antivirus performing real-time scanning and heuristics."),
        "uk": ("Служба Antimalware (msmpeng)", "Головний скануючий рушій Захисника Windows, що виконує захист у реальному часі та евристичний аналіз."),
        "he": ("שירות האנטי-וירוס (msmpeng)", "מנוע הסריקה הראשי של Microsoft Defender המבצע הגנה בזמן אמת וניתוח היוריסטי של קבצים.")
    },
    "runtimebroker.exe": {
        "en": ("Runtime Broker", "Manages permissions for UWP Windows Store apps, ensuring restricted access to cameras, mics, and storage."),
        "uk": ("Runtime Broker", "Системний посередник, що керує дозволами додатків Windows Store (доступ до камери, мікрофона, файлів)."),
        "he": ("Runtime Broker", "מנהל הרשאות עבור אפליקציות חנות Windows (גישה למצלמה, מיקרופון ומערכת הקבצים).")
    },
    "searchindexer.exe": {
        "en": ("Windows Search Indexer", "Builds background search indexes for files, emails, and metadata to accelerate desktop searches."),
        "uk": ("Індексатор Пошуку Windows", "Фонова служба індексації файлів, листів та метаданих для миттєвого пошуку в системі."),
        "he": ("אינדוקס החיפוש של Windows", "בונה אינדקס חיפוש ברקע עבור קבצים, הודעות דוא\"ל ומטא-דאטה להאצת החיפוש במחשב.")
    },
    "spoolsv.exe": {
        "en": ("Print Spooler Service", "Manages print queues, coordinates document rendering, and directs printer drivers."),
        "uk": ("Диспетчер Друку (spoolsv)", "Служба керування чергами друку, завантаженням драйверів та надсиланням документів на принтери."),
        "he": ("שירות ניהול ההדפסה (spoolsv)", "מנהל תורי הדפסה במערכת, מתאם עיבוד מסמכים ותקשורת מול מנהלי התקנים של מדפסות.")
    },
    "system": {
        "en": ("System Kernel Process (PID 4)", "Special process hosting kernel-mode threads, hardware drivers, and system execution contexts."),
        "uk": ("Системний Процес (PID 4)", "Спеціальний процес, що вміщує потоки ядра ОС, драйвери апаратних пристроїв та контексти виконання."),
        "he": ("תהליך ליבת המערכת (PID 4)", "תהליך מיוחד המארח תהליכוני ליבה, מנהלי התקני חומרה והקשרי ביצוע של המערכת.")
    },
    "registry": {
        "en": ("Windows Registry Process", "Kernel-mode host process optimizing Windows registry hive caching and memory compression."),
        "uk": ("Процес Реєстру Windows", "Службовий процес ядра, що оптимізує кешування гілок реєстру та стиснення пам'яті."),
        "he": ("תהליך רישום המערכת (Registry)", "תהליך ליבה המייעל את שמירת המטמון של מפתחות הרישום ודחיסת הזיכרון במערכת.")
    },
    "cloudflared.exe": {
        "en": ("Cloudflare Tunnel Daemon", "Encrypted outbound zero-trust proxy daemon connecting local web services to Cloudflare edge network."),
        "uk": ("Демон Cloudflare Tunnel", "Служба зашифрованого тунелю Zero Trust для безпечного підключення локальних сервісів до Cloudflare."),
        "he": ("סוכן מנהרת Cloudflare", "תהליך רקע מוצפן של Zero Trust המחבר שירותי רשת מקומיים ישירות לרשת הענן של Cloudflare.")
    },
    "ctfmon.exe": {
        "en": ("CTF Loader / Language Bar", "Controls Alternative User Input text processor and Microsoft Text Services Framework (TSF)."),
        "uk": ("Завантажувач CTF (ctfmon)", "Керує мовною панеллю, розкладками клавіатури, рукописним введенням та розпізнаванням мови в Windows."),
        "he": ("שירות קלט טקסט ושפות (ctfmon)", "מנהל את שורת השפות, פריסות המקלדת ושירותי קלט הטקסט המתקדמים של Windows (TSF).")
    }
}

# Генерация полных словарей
tooltips_en = {}
tooltips_uk = {}
tooltips_he = {}
tooltips_ru = {}

for key, ru_item in ru_all.items():
    icon = ru_item.get("icon", "💡")
    ru_cat = ru_item.get("category", "Справка")
    ru_title = ru_item.get("title", key)
    ru_summary = ru_item.get("summary", "")

    # RU
    tooltips_ru[key] = {
        "title": ru_title,
        "summary": ru_summary,
        "category": ru_cat,
        "icon": icon
    }

    # Поиск базового ключа для перевода (если это .exe или без .exe)
    base_key = key
    if key not in BASE_TRANSLATIONS:
        if f"{key}.exe" in BASE_TRANSLATIONS:
            base_key = f"{key}.exe"
        elif key.endswith(".exe") and key[:-4] in BASE_TRANSLATIONS:
            base_key = key[:-4]

    trans = BASE_TRANSLATIONS.get(base_key)

    if trans:
        en_t, en_s = trans["en"]
        uk_t, uk_s = trans["uk"]
        he_t, he_s = trans["he"]
    else:
        # Fallback если не найдено в явном списке
        en_t, en_s = ru_title, ru_summary
        uk_t, uk_s = ru_title, ru_summary
        he_t, he_s = ru_title, ru_summary

    tooltips_en[key] = {
        "title": en_t,
        "summary": en_s,
        "category": get_cat(ru_cat, "en"),
        "icon": icon
    }

    tooltips_uk[key] = {
        "title": uk_t,
        "summary": uk_s,
        "category": get_cat(ru_cat, "uk"),
        "icon": icon
    }

    tooltips_he[key] = {
        "title": he_t,
        "summary": he_s,
        "category": get_cat(ru_cat, "he"),
        "icon": icon
    }

print(f"Prepared translations for {len(tooltips_ru)} keys across 4 languages.")

# Функция интеграции в файлы локалей
def update_locale_file(filepath, tooltips_dict):
    if filepath.exists():
        data = json.load(open(filepath, encoding="utf-8"))
    else:
        data = {}
    data["tooltips"] = tooltips_dict
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated {filepath} with {len(tooltips_dict)} tooltips.")

update_locale_file(RU_PATH, tooltips_ru)
update_locale_file(EN_PATH, tooltips_en)
update_locale_file(UK_PATH, tooltips_uk)
update_locale_file(HE_PATH, tooltips_he)

print("All 4 locale files updated successfully.")
