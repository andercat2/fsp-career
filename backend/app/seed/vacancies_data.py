"""Демонстрационные компании и описания вакансий (вымышленные). Структурированные поля заполняются
NLP-разбором текста — так же, как это делает работодатель в интерфейсе."""

COMPANIES = [
    {
        "key": "technopulse", "email": "employer@demo.ru", "name": "ТехноПульс", "industry": "E-commerce и ритейл",
        "city": "Казань", "size": "200–500 сотрудников", "website": "technopulse.example",
        "contact_name": "Анна Сергеевна, HR-партнёр", "contact_telegram": "@technopulse_hr",
        "contact_phone": "+7 843 000-00-01",
        "description": "Маркетплейс электронной техники: 3 млн покупателей, собственная логистика и платёжный сервис. "
                       "Инженерная команда — 120 человек, продуктовые команды по 6–8 человек.",
    },
    {
        "key": "fintechlab", "email": "hr@fintechlab.example", "name": "Финтех Лаб", "industry": "Финтех и банки",
        "city": "Москва", "size": "50–200 сотрудников", "website": "fintechlab.example",
        "contact_name": "Дмитрий, техлид", "contact_telegram": "@fintechlab_jobs", "contact_phone": None,
        "description": "Платформа онлайн-кредитования для малого бизнеса. Высокие требования к надёжности и безопасности.",
    },
    {
        "key": "pixel", "email": "jobs@pixel-games.example", "name": "Пиксель Геймз", "industry": "GameDev",
        "city": "Санкт-Петербург", "size": "50–200 сотрудников", "website": "pixel-games.example",
        "contact_name": "Мария, рекрутер", "contact_telegram": "@pixel_recruit", "contact_phone": None,
        "description": "Студия браузерных и мобильных игр. Делаем собственный игровой портал и сервисы для игроков.",
    },
    {
        "key": "medtech", "email": "career@medtech.example", "name": "МедТех Решения", "industry": "HealthTech",
        "city": "Новосибирск", "size": "50–200 сотрудников", "website": "medtech.example",
        "contact_name": "Ольга, HR", "contact_telegram": "@medtech_hr", "contact_phone": None,
        "description": "Системы поддержки врачебных решений: анализ медицинских изображений и данных пациентов.",
    },
    {
        "key": "logistics", "email": "it@logplus.example", "name": "Логистика Плюс", "industry": "Логистика",
        "city": "Екатеринбург", "size": "1000+ сотрудников", "website": "logplus.example",
        "contact_name": "Игорь, руководитель разработки", "contact_telegram": "@logplus_it", "contact_phone": None,
        "description": "Федеральный логистический оператор. Цифровизируем склады и маршрутизацию доставки.",
    },
]

VACANCIES = [
    {
        "company": "technopulse", "published": True,
        "title": "Middle Python-разработчик (платёжный сервис)",
        "text": """Команда платёжного сервиса ТехноПульс ищет Python-разработчика уровня Middle.
Чем предстоит заниматься:
- развивать сервис приёма платежей и возвратов (Python, FastAPI);
- проектировать REST API для мобильного приложения и сайта;
- оптимизировать запросы к PostgreSQL, работать с Redis и Kafka.
Требования:
- опыт коммерческой разработки на Python от 3 лет;
- уверенное знание SQL и PostgreSQL, понимание транзакций и индексов;
- опыт с микросервисной архитектурой, Docker.
Будет плюсом: Kubernetes, опыт участия в соревнованиях ФСП или хакатонах.
Условия: гибридный формат, офис в Казани, зарплата от 230 000 до 320 000 ₽.""",
        "team": "Команда из 7 человек: 4 бэкенд-разработчика, QA, аналитик и тимлид.",
    },
    {
        "company": "technopulse", "published": True,
        "title": "Senior Frontend-разработчик (React)",
        "text": """Ищем сильного фронтенд-разработчика в команду витрины маркетплейса.
Задачи: архитектура клиентской части на React и TypeScript, дизайн-система, производительность (Web Vitals), SSR на Next.js.
Требования: опыт от 5 лет, глубокое знание JavaScript, TypeScript, React, Redux или аналогов, CSS, понимание работы браузера.
Желательно: опыт настройки Webpack/Vite, тестирование (Jest), менторство.
Удалённо или гибрид, вилка 330 000 – 450 000 руб.""",
        "team": "Фронтенд-гильдия из 12 человек, своя дизайн-система.",
    },
    {
        "company": "technopulse", "published": False,
        "title": "Junior QA-инженер",
        "text": """Нужен начинающий QA-инженер в команду складской логистики.
Задачи: тест-дизайн, ручное тестирование веб-интерфейсов и API (Postman), заведение баг-репортов в Jira, участие в регрессе.
Требования: понимание техник тест-дизайна (граничные значения, классы эквивалентности), базовый SQL.
Будет плюсом: Python и pytest для автотестов.
Офис в Казани, от 90 000 до 120 000 ₽.""",
        "team": "",
    },
    {
        "company": "technopulse", "published": True,
        "title": "Продуктовый аналитик данных",
        "text": """В команду роста нужен аналитик данных уровня Middle.
Задачи: продуктовые метрики (retention, конверсии, LTV), дизайн и анализ A/B-тестов, дашборды в DataLens.
Требования: отличный SQL (ClickHouse), статистика и проверка гипотез, Python (pandas) для исследований.
Будет плюсом: опыт CUPED и других методов снижения дисперсии.
Гибридный формат, Казань или удалённо, 200 000 – 270 000 ₽.""",
        "team": "Аналитический центр компетенций из 9 человек.",
    },
    {
        "company": "fintechlab", "published": True,
        "title": "Go-разработчик (Middle+)",
        "text": """Финтех Лаб ищет Go-разработчика в команду кредитного конвейера.
Стек: Go, PostgreSQL, Kafka, gRPC, Kubernetes. Задачи: высоконагруженные микросервисы скоринга, интеграции с бюро кредитных историй.
Требования: опыт на Go от 2 лет, понимание конкурентности (горутины, каналы), SQL, принципы безопасности приложений.
Желательно: опыт с Redis, observability (Prometheus, Grafana).
Полностью удалённо, зарплата от 280 000 до 380 000 ₽.""",
        "team": "",
    },
    {
        "company": "fintechlab", "published": True,
        "title": "DevOps / SRE-инженер",
        "text": """Нужен Senior DevOps/SRE для платформы онлайн-кредитования.
Задачи: эксплуатация Kubernetes-кластеров, CI/CD в GitLab, Terraform, мониторинг и алертинг (Prometheus, Grafana), SLO и разбор инцидентов.
Требования: Linux, сети, Docker, Kubernetes, опыт on-call, опыт от 5 лет.
Москва, гибрид, 350 000 – 480 000 ₽.""",
        "team": "",
    },
    {
        "company": "pixel", "published": True,
        "title": "Fullstack-разработчик (Node.js + React)",
        "text": """Пиксель Геймз ищет fullstack-разработчика для игрового портала.
Фронтенд на React, бэкенд на Node.js (NestJS), PostgreSQL и Redis. Делаем фичи от интерфейса до базы данных.
Требования: JavaScript/TypeScript, React, Node.js, SQL, опыт от 2 лет.
Будет плюсом: WebSocket, опыт в GameDev.
Санкт-Петербург или удалённо, от 200 000 до 280 000 руб.""",
        "team": "",
    },
    {
        "company": "medtech", "published": True,
        "title": "Data Scientist (компьютерное зрение)",
        "text": """МедТех Решения ищет Data Scientist для анализа медицинских изображений.
Задачи: обучение моделей сегментации и классификации (PyTorch), подготовка датасетов, валидация качества, вывод моделей в продакшен.
Требования: Python, PyTorch, компьютерное зрение, статистика, метрики качества классификации, опыт от 3 лет.
Желательно: MLOps (MLflow), опыт с медицинскими данными, призовые места в соревнованиях по машинному обучению.
Новосибирск, гибрид, 280 000 – 380 000 ₽.""",
        "team": "",
    },
    {
        "company": "logistics", "published": True,
        "title": "Junior Java-разработчик",
        "text": """Логистика Плюс приглашает Junior Java-разработчика в команду складских систем.
Стек: Java 21, Spring Boot, PostgreSQL, Kafka. Задачи: доработка сервисов учёта, unit-тесты, участие в код-ревью.
Требования: Java, ООП, SQL, Git, базовые алгоритмы и структуры данных.
Будет плюсом: Docker, участие в олимпиадах и соревнованиях по программированию.
Екатеринбург, офис, 110 000 – 150 000 ₽.""",
        "team": "",
    },
]

TASKS = [
    {"company": "technopulse", "specialization": "backend", "grades": [], "kind": "approach",
     "title": "Идемпотентность приёма платежей",
     "description": "Платёжный шлюз иногда повторяет callback об успешной оплате 2–3 раза. Опишите, как сделать "
                    "обработку идемпотентной: какие данные хранить, какие ограничения в БД нужны, что делать при гонке.",
     "expected_answer": "Хранить идентификатор платежа/события, уникальный индекс, транзакция, SELECT FOR UPDATE или "
                        "INSERT ON CONFLICT DO NOTHING, статусная машина, идемпотентный ключ, повторный ответ тем же результатом.",
     "time_estimate_min": 30},
    {"company": "technopulse", "specialization": "frontend", "grades": [], "kind": "approach",
     "title": "Ускорить карточку товара",
     "description": "LCP карточки товара на мобильных — 4,2 с. Опишите план диагностики и 3–5 конкретных оптимизаций.",
     "expected_answer": "Lighthouse, профилирование, приоритизация LCP-изображения, preload, сжатие и современные форматы "
                        "изображений, SSR, code splitting, lazy loading, кеширование, уменьшение JS.",
     "time_estimate_min": 30},
    {"company": "technopulse", "specialization": "data_analyst", "grades": [], "kind": "solve",
     "title": "Retention по когортам",
     "description": "Есть таблица events(user_id, event_date). Напишите SQL, считающий retention 7-го дня по недельным "
                    "когортам первой активности.",
     "expected_answer": "WITH first AS (SELECT user_id, MIN(event_date) AS d0 FROM events GROUP BY user_id) SELECT "
                        "date_trunc('week', d0), COUNT(DISTINCT CASE WHEN event_date = d0 + 7 THEN user_id END) / "
                        "COUNT(DISTINCT user_id) FROM first JOIN events USING (user_id) GROUP BY 1",
     "time_estimate_min": 40},
    {"company": "fintechlab", "specialization": "backend", "grades": ["middle", "senior"], "kind": "approach",
     "title": "Лимитер запросов к бюро кредитных историй",
     "description": "Внешнее бюро разрешает 50 запросов в секунду на всех. У нас 12 подов скоринга. Как ограничить "
                    "суммарную нагрузку и не терять заявки?",
     "expected_answer": "Распределённый rate limiter (token bucket в Redis), очередь заявок, ретраи с backoff, приоритеты, "
                        "circuit breaker, метрики и алерты.",
     "time_estimate_min": 30},
    {"company": "fintechlab", "specialization": "devops", "grades": [], "kind": "approach",
     "title": "Алерты по SLO",
     "description": "SLO доступности API — 99,9% за 30 дней. Предложите схему алертинга по burn rate, чтобы будить "
                    "дежурного только при реальной угрозе SLO.",
     "expected_answer": "Multi-window multi-burn-rate алерты: быстрое окно 1 ч/5 мин с burn rate 14.4, медленное 6 ч/30 мин "
                        "с burn rate 6, тикеты для 3 дней, считать по error ratio, Prometheus recording rules.",
     "time_estimate_min": 25},
    {"company": "pixel", "specialization": "fullstack", "grades": [], "kind": "approach",
     "title": "Таблица лидеров в реальном времени",
     "description": "Нужно показывать топ-100 игроков с обновлением в реальном времени для 50 тыс. онлайн. "
                    "Опишите архитектуру бэкенда и фронтенда.",
     "expected_answer": "Redis sorted set, WebSocket или SSE, батчинг обновлений, кеш, пагинация, виртуализация списка "
                        "на фронте, throttling.",
     "time_estimate_min": 30},
    {"company": "medtech", "specialization": "ml", "grades": [], "kind": "approach",
     "title": "Несбалансированные классы в диагностике",
     "description": "Патология встречается на 2% снимков. Как обучать и оценивать модель, чтобы врачу было полезно?",
     "expected_answer": "Стратифицированная валидация, PR-AUC, recall при фиксированной precision, взвешивание классов "
                        "или focal loss, аугментации, калибровка, выбор порога с врачами, анализ ошибок.",
     "time_estimate_min": 30},
    {"company": "logistics", "specialization": "qa", "grades": [], "kind": "solve",
     "title": "Тест-кейсы для поля «вес посылки»",
     "description": "Поле принимает вес от 0,1 до 30 кг с шагом 0,1. Составьте набор тестов по граничным значениям и "
                    "классам эквивалентности.",
     "expected_answer": "0, 0.1, 0.2, 29.9, 30, 30.1, отрицательное, пустое, буквы, 0.15 (шаг), 15 как типичное.",
     "time_estimate_min": 20},
]
