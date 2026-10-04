"""Справочники платформы: специализации, грейды, тестовые домены, блюпринты тестов, отрасли.

Категория кандидата = (специализация, грейд). Грейд определяется тестом на общей шкале способностей θ (IRT),
поэтому кандидаты одной категории сопоставимы независимо от того, какие конкретно задания им достались.
"""
from __future__ import annotations

GRADES = [
    {
        "code": "intern",
        "name": "Стажёр",
        "short": "Intern",
        "experience": "до 1 года",
        "description": "Знает основы, решает типовые задачи под руководством.",
    },
    {
        "code": "junior",
        "name": "Junior",
        "short": "Junior",
        "experience": "1–2 года",
        "description": "Самостоятельно решает типовые задачи, нуждается в ревью архитектурных решений.",
    },
    {
        "code": "middle",
        "name": "Middle",
        "short": "Middle",
        "experience": "2–5 лет",
        "description": "Самостоятельно ведёт задачи от постановки до продакшена, понимает компромиссы.",
    },
    {
        "code": "senior",
        "name": "Senior",
        "short": "Senior",
        "experience": "5+ лет",
        "description": "Проектирует системы, отвечает за качество и надёжность, менторит команду.",
    },
]
GRADE_CODES = [g["code"] for g in GRADES]
GRADE_INDEX = {g: i for i, g in enumerate(GRADE_CODES)}
GRADE_NAMES = {g["code"]: g["name"] for g in GRADES}

# Пороги грейдов на шкале θ (N(0,1) — «средний рынок»). Грейд g соответствует [CUTS[g], CUTS[g+1]).
THETA_CUTS = [-1.0, 0.0, 1.0]


def grade_band(grade: str) -> tuple[float, float]:
    i = GRADE_INDEX[grade]
    lo = THETA_CUTS[i - 1] if i > 0 else float("-inf")
    hi = THETA_CUTS[i] if i < len(THETA_CUTS) else float("inf")
    return lo, hi


def grade_center(grade: str) -> float:
    return {"intern": -1.6, "junior": -0.5, "middle": 0.5, "senior": 1.6}[grade]


def theta_to_grade(theta: float) -> str:
    for i, cut in enumerate(THETA_CUTS):
        if theta < cut:
            return GRADE_CODES[i]
    return GRADE_CODES[-1]


DOMAINS = {
    "algorithms": "Алгоритмы и структуры данных",
    "python": "Python",
    "java": "Java",
    "go": "Go",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "web_layout": "HTML и CSS",
    "browser": "Браузер и веб-платформа",
    "sql": "SQL",
    "databases": "Базы данных и транзакции",
    "http_api": "HTTP и проектирование API",
    "architecture": "Архитектура и масштабирование",
    "security": "Безопасность приложений",
    "linux": "Linux и shell",
    "networks": "Сети",
    "containers": "Docker и контейнеры",
    "kubernetes": "Kubernetes",
    "cicd": "CI/CD и Git",
    "observability": "Мониторинг и надёжность",
    "statistics": "Статистика и вероятности",
    "ml": "Машинное обучение",
    "deep_learning": "Глубокое обучение",
    "data_tools": "pandas и NumPy",
    "analytics": "Продуктовая аналитика и A/B",
    "testing_theory": "Тест-дизайн",
    "test_automation": "Автоматизация тестирования",
}

LANGUAGES = {
    "python": "Python",
    "java": "Java",
    "go": "Go",
    "javascript": "JavaScript / TypeScript",
}

# "$lang" подставляется основным языком кандидата (выбирается в опросе).
SPECIALIZATIONS = [
    {
        "code": "backend",
        "name": "Backend-разработчик",
        "direction": "Разработка",
        "description": "Серверная логика, API, базы данных, интеграции.",
        "languages": ["python", "java", "go", "javascript"],
        "blueprint": {
            "algorithms": 0.14, "$lang": 0.22, "sql": 0.13, "databases": 0.10, "http_api": 0.12,
            "architecture": 0.12, "security": 0.09, "linux": 0.04, "cicd": 0.04,
        },
        "core_skills": ["sql", "postgresql", "rest", "git", "docker", "redis", "kafka"],
    },
    {
        "code": "frontend",
        "name": "Frontend-разработчик",
        "direction": "Разработка",
        "description": "Клиентская часть веб-приложений, интерфейсы, производительность в браузере.",
        "languages": ["javascript"],
        "blueprint": {
            "javascript": 0.25, "typescript": 0.09, "react": 0.17, "web_layout": 0.15, "browser": 0.14,
            "http_api": 0.07, "algorithms": 0.08, "security": 0.05,
        },
        "core_skills": ["javascript", "typescript", "react", "html", "css", "webpack", "vite"],
    },
    {
        "code": "fullstack",
        "name": "Fullstack-разработчик",
        "direction": "Разработка",
        "description": "Полный цикл веб-разработки: от интерфейса до API и базы данных.",
        "languages": ["javascript", "python", "java", "go"],
        "blueprint": {
            "$lang": 0.13, "javascript": 0.14, "react": 0.12, "web_layout": 0.08, "browser": 0.06,
            "sql": 0.12, "databases": 0.06, "http_api": 0.12, "architecture": 0.09, "algorithms": 0.08,
        },
        "core_skills": ["javascript", "react", "sql", "rest", "docker", "git"],
    },
    {
        "code": "ml",
        "name": "Data Scientist / ML-инженер",
        "direction": "Данные и ИИ",
        "description": "Модели машинного обучения, эксперименты, вывод моделей в продакшен.",
        "languages": ["python"],
        "blueprint": {
            "python": 0.16, "statistics": 0.17, "ml": 0.25, "deep_learning": 0.13, "data_tools": 0.12,
            "sql": 0.08, "algorithms": 0.09,
        },
        "core_skills": ["python", "pandas", "numpy", "scikit_learn", "pytorch", "sql", "statistics"],
    },
    {
        "code": "data_analyst",
        "name": "Аналитик данных",
        "direction": "Данные и ИИ",
        "description": "SQL, метрики продукта, A/B-тесты, отчётность и BI.",
        "languages": ["python"],
        "blueprint": {
            "sql": 0.28, "statistics": 0.22, "analytics": 0.22, "data_tools": 0.14, "python": 0.08, "ml": 0.06,
        },
        "core_skills": ["sql", "excel", "python", "pandas", "tableau", "ab_testing", "statistics"],
    },
    {
        "code": "devops",
        "name": "DevOps / SRE-инженер",
        "direction": "Инфраструктура",
        "description": "CI/CD, контейнеризация, оркестрация, мониторинг и надёжность.",
        "languages": ["python", "go"],
        "blueprint": {
            "linux": 0.18, "networks": 0.14, "containers": 0.16, "kubernetes": 0.14, "cicd": 0.12,
            "observability": 0.14, "security": 0.06, "$lang": 0.06,
        },
        "core_skills": ["linux", "docker", "kubernetes", "terraform", "ansible", "prometheus", "gitlab_ci"],
    },
    {
        "code": "qa",
        "name": "QA-инженер",
        "direction": "Тестирование",
        "description": "Тест-дизайн, ручное и автоматизированное тестирование, качество релизов.",
        "languages": ["python", "java", "javascript"],
        "blueprint": {
            "testing_theory": 0.30, "test_automation": 0.18, "http_api": 0.14, "sql": 0.12, "$lang": 0.10,
            "browser": 0.06, "cicd": 0.05, "algorithms": 0.05,
        },
        "core_skills": ["test_design", "postman", "selenium", "pytest", "sql", "jira", "api_testing"],
    },
]
SPEC_BY_CODE = {s["code"]: s for s in SPECIALIZATIONS}
SPEC_NAMES = {s["code"]: s["name"] for s in SPECIALIZATIONS}


def resolve_blueprint(spec: str, language: str | None) -> dict[str, float]:
    """Блюпринт теста: доли доменов. "$lang" заменяется доменом основного языка кандидата."""
    sp = SPEC_BY_CODE[spec]
    lang = language if language in sp["languages"] else sp["languages"][0]
    bp: dict[str, float] = {}
    for dom, w in sp["blueprint"].items():
        key = lang if dom == "$lang" else dom
        bp[key] = bp.get(key, 0.0) + w
    total = sum(bp.values())
    return {k: round(v / total, 4) for k, v in bp.items()}


INDUSTRIES = [
    "Финтех и банки", "E-commerce и ритейл", "GameDev", "GovTech", "EdTech", "HealthTech", "Телеком",
    "Промышленность", "Медиа и развлечения", "Кибербезопасность", "Логистика", "Аутсорс и интеграторы",
]

WORK_FORMATS = {"office": "Офис", "hybrid": "Гибрид", "remote": "Удалённо"}

TEAM_ROLES = {
    "developer": "Разработка",
    "code_review": "Код-ревью",
    "mentoring": "Менторство",
    "tech_lead": "Техлидерство",
    "architecture": "Проектирование архитектуры",
    "devops_practices": "Настройка CI/CD",
    "analysis": "Анализ требований",
    "testing": "Тестирование",
    "research": "Исследования и эксперименты",
    "team_lead": "Руководство командой",
}

SOFT_SKILLS = {
    "communication": ("Коммуникабельность", ["коммуникаб", "communication", "общительн"]),
    "teamwork": ("Командная работа", ["командн", "teamwork", "team player", "работа в команде"]),
    "responsibility": ("Ответственность", ["ответствен", "responsib"]),
    "learning": ("Обучаемость", ["обучаем", "быстро учусь", "fast learner", "самообуч"]),
    "leadership": ("Лидерство", ["лидер", "leadership"]),
    "critical_thinking": ("Аналитическое мышление", ["аналитическ", "analytical", "критическ"]),
    "time_management": ("Тайм-менеджмент", ["тайм-менедж", "time management", "организован"]),
    "stress_resistance": ("Стрессоустойчивость", ["стрессоустойч"]),
    "initiative": ("Инициативность", ["инициатив", "proactive", "проактив"]),
    "mentoring": ("Наставничество", ["наставни", "менторств", "mentor"]),
}

DECLINE_REASONS = {
    "salary": "Не устраивает уровень дохода",
    "stack": "Не подходит стек/задачи",
    "format": "Не подходит формат работы или локация",
    "company": "Не интересна компания/отрасль",
    "not_looking": "Сейчас не ищу работу",
    "other": "Другое",
}

# Дисциплины ФСП и их релевантность специализациям (0..1) — используется в ранжировании.
FSP_DISCIPLINES = {
    "product": "Продуктовое программирование",
    "algorithmic": "Алгоритмическое программирование",
    "security": "Программирование систем информационной безопасности",
    "drones": "Программирование беспилотных авиационных систем",
    "robotics": "Программирование робототехники",
}
FSP_RELEVANCE = {
    "backend": {"product": 1.0, "algorithmic": 0.9, "security": 0.7, "drones": 0.4, "robotics": 0.4},
    "frontend": {"product": 1.0, "algorithmic": 0.6, "security": 0.4, "drones": 0.2, "robotics": 0.2},
    "fullstack": {"product": 1.0, "algorithmic": 0.8, "security": 0.5, "drones": 0.3, "robotics": 0.3},
    "ml": {"product": 0.7, "algorithmic": 1.0, "security": 0.4, "drones": 0.7, "robotics": 0.7},
    "data_analyst": {"product": 0.8, "algorithmic": 0.7, "security": 0.3, "drones": 0.3, "robotics": 0.3},
    "devops": {"product": 0.7, "algorithmic": 0.5, "security": 1.0, "drones": 0.4, "robotics": 0.4},
    "qa": {"product": 0.9, "algorithmic": 0.5, "security": 0.7, "drones": 0.3, "robotics": 0.3},
}
FSP_LEVELS = {
    "regional": "Региональный",
    "interregional": "Межрегиональный",
    "national": "Всероссийский",
    "international": "Международный",
}
