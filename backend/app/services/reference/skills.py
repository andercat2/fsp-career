"""Онтология навыков: канонический id, отображаемое имя, группа, синонимы (RU/EN) и тестовые домены,
которыми навык может быть подтверждён. Используется разбором резюме, разбором вакансий и подбором."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    group: str
    synonyms: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    specs: tuple[str, ...] = field(default=())  # специализации, для которых навык характерен


def _s(id_, name, group, syn=(), domains=(), specs=()):
    return Skill(id_, name, group, tuple(syn), tuple(domains), tuple(specs))


LANG, FW, DB, INFRA, DATA, QA, FE, PRACT, TOOLS = (
    "Языки", "Фреймворки и библиотеки", "Базы данных", "Инфраструктура", "Данные и ML", "Тестирование",
    "Frontend", "Практики", "Инструменты",
)

SKILLS: list[Skill] = [
    # Языки
    _s("python", "Python", LANG, ["python", "питон", "python3", "пайтон"], ["python"], ["backend", "ml", "data_analyst", "qa", "devops"]),
    _s("java", "Java", LANG, ["java", "java se", "java ee", "джава"], ["java"], ["backend", "qa"]),
    _s("kotlin", "Kotlin", LANG, ["kotlin", "котлин"], ["java"], ["backend"]),
    _s("go", "Go", LANG, ["golang", "go lang", "go-разработ", "go developer", "на go"], ["go"], ["backend", "devops"]),
    _s("javascript", "JavaScript", LANG, ["javascript", "js", "ecmascript", "es6", "es2015", "джаваскрипт"], ["javascript"], ["frontend", "fullstack"]),
    _s("typescript", "TypeScript", LANG, ["typescript"], ["typescript"], ["frontend", "fullstack"]),
    _s("csharp", "C#", LANG, ["c#", "csharp", "c sharp", ".net", "dotnet", "asp.net"], [], ["backend"]),
    _s("cpp", "C++", LANG, ["c++", "cpp", "плюсы"], [], ["backend"]),
    _s("c", "C", LANG, ["язык c", "ansi c", "c99", "c11"], [], []),
    _s("rust", "Rust", LANG, ["rust"], [], ["backend"]),
    _s("php", "PHP", LANG, ["php", "laravel", "symfony"], [], ["backend"]),
    _s("ruby", "Ruby", LANG, ["ruby", "rails", "ruby on rails"], [], ["backend"]),
    _s("scala", "Scala", LANG, ["scala"], [], ["backend"]),
    _s("swift", "Swift", LANG, ["swift", "swiftui"], [], []),
    _s("bash", "Bash", LANG, ["bash", "shell", "sh-скрипт", "shell scripting", "zsh"], ["linux"], ["devops"]),
    _s("sql", "SQL", LANG, ["sql", "t-sql", "pl/sql", "plpgsql", "pl/pgsql", "sql-запрос"], ["sql"], ["backend", "data_analyst", "qa", "ml"]),
    _s("r_lang", "R", LANG, ["язык r", "r studio", "rstudio"], ["statistics"], ["data_analyst"]),
    # Backend-фреймворки
    _s("django", "Django", FW, ["django", "drf", "django rest framework"], ["python", "http_api"], ["backend"]),
    _s("fastapi", "FastAPI", FW, ["fastapi"], ["python", "http_api"], ["backend"]),
    _s("flask", "Flask", FW, ["flask"], ["python", "http_api"], ["backend"]),
    _s("aiohttp", "aiohttp / asyncio", FW, ["aiohttp", "asyncio", "async/await"], ["python"], ["backend"]),
    _s("sqlalchemy", "SQLAlchemy", FW, ["sqlalchemy"], ["python", "databases"], ["backend"]),
    _s("celery", "Celery", FW, ["celery"], ["python", "architecture"], ["backend"]),
    _s("spring", "Spring", FW, ["spring", "spring boot", "springboot", "spring framework"], ["java", "http_api"], ["backend"]),
    _s("hibernate", "Hibernate / JPA", FW, ["hibernate", "jpa"], ["java", "databases"], ["backend"]),
    _s("gin", "Gin / Echo", FW, ["gin", "echo framework", "fiber"], ["go", "http_api"], ["backend"]),
    _s("nodejs", "Node.js", FW, ["node.js", "nodejs", "node js", "express", "express.js", "nestjs", "nest.js"], ["javascript", "http_api"], ["backend", "fullstack"]),
    _s("grpc", "gRPC", FW, ["grpc", "protobuf", "protocol buffers"], ["http_api", "architecture"], ["backend"]),
    _s("graphql", "GraphQL", FW, ["graphql", "apollo"], ["http_api"], ["backend", "frontend"]),
    _s("rest", "REST API", PRACT, ["rest", "restful", "rest api", "openapi", "swagger"], ["http_api"], ["backend", "fullstack", "qa"]),
    _s("microservices", "Микросервисы", PRACT, ["микросервис", "microservice", "микросервисная"], ["architecture"], ["backend"]),
    _s("system_design", "Проектирование систем", PRACT, ["system design", "проектирование систем", "highload", "хайлоад", "высоконагруж"], ["architecture"], ["backend"]),
    _s("oop", "ООП и паттерны", PRACT, ["ооп", "oop", "solid", "паттерны проектирования", "design patterns", "gof"], ["architecture"], ["backend"]),
    _s("algorithms", "Алгоритмы и структуры данных", PRACT, ["алгоритм", "структуры данных", "algorithms", "data structures", "leetcode", "олимпиадн"], ["algorithms"], []),
    _s("security_web", "Безопасность веб-приложений", PRACT, ["owasp", "xss", "csrf", "sql injection", "sql-инъекц", "appsec", "безопасность приложений"], ["security"], ["backend"]),
    _s("oauth", "OAuth2 / OIDC / Keycloak", PRACT, ["oauth", "oauth2", "openid connect", "oidc", "keycloak", "jwt"], ["security", "http_api"], ["backend"]),
    # БД и брокеры
    _s("postgresql", "PostgreSQL", DB, ["postgresql", "postgres", "постгрес"], ["sql", "databases"], ["backend"]),
    _s("mysql", "MySQL", DB, ["mysql", "mariadb"], ["sql", "databases"], ["backend"]),
    _s("oracle", "Oracle DB", DB, ["oracle"], ["sql", "databases"], ["backend"]),
    _s("mssql", "MS SQL Server", DB, ["ms sql", "mssql", "sql server"], ["sql", "databases"], ["backend"]),
    _s("mongodb", "MongoDB", DB, ["mongodb", "mongo"], ["databases"], ["backend"]),
    _s("redis", "Redis", DB, ["redis"], ["databases", "architecture"], ["backend"]),
    _s("clickhouse", "ClickHouse", DB, ["clickhouse", "кликхаус"], ["sql", "databases"], ["backend", "data_analyst"]),
    _s("elasticsearch", "Elasticsearch", DB, ["elasticsearch", "elastic", "opensearch"], ["databases"], ["backend"]),
    _s("cassandra", "Cassandra", DB, ["cassandra"], ["databases"], ["backend"]),
    _s("kafka", "Kafka", DB, ["kafka", "кафка"], ["architecture"], ["backend"]),
    _s("rabbitmq", "RabbitMQ", DB, ["rabbitmq", "rabbit mq", "amqp"], ["architecture"], ["backend"]),
    _s("db_design", "Проектирование БД", PRACT, ["проектирование бд", "нормализац", "индекс", "транзакц", "database design", "isolation level"], ["databases"], ["backend"]),
    # Frontend
    _s("html", "HTML", FE, ["html", "html5", "вёрстка", "верстка"], ["web_layout"], ["frontend"]),
    _s("css", "CSS", FE, ["css", "css3", "scss", "sass", "less", "flexbox", "grid layout", "tailwind", "bem"], ["web_layout"], ["frontend"]),
    _s("react", "React", FE, ["react", "react.js", "reactjs", "react hooks", "next.js", "nextjs"], ["react"], ["frontend", "fullstack"]),
    _s("redux", "Redux / MobX / Zustand", FE, ["redux", "mobx", "zustand", "redux toolkit", "effector"], ["react"], ["frontend"]),
    _s("vue", "Vue.js", FE, ["vue", "vue.js", "vuex", "pinia", "nuxt"], ["javascript"], ["frontend"]),
    _s("angular", "Angular", FE, ["angular", "rxjs"], ["typescript"], ["frontend"]),
    _s("webpack", "Webpack / Vite", FE, ["webpack", "vite", "rollup", "esbuild", "babel"], ["browser"], ["frontend"]),
    _s("browser_apis", "Web API браузера", FE, ["dom", "web api", "service worker", "websocket", "indexeddb", "localstorage"], ["browser"], ["frontend"]),
    _s("web_perf", "Производительность веба", FE, ["web vitals", "lighthouse", "производительность фронт", "оптимизация загрузки"], ["browser"], ["frontend"]),
    _s("a11y", "Доступность (a11y)", FE, ["a11y", "accessibility", "доступность", "wcag", "aria"], ["web_layout"], ["frontend"]),
    _s("figma", "Figma", FE, ["figma", "фигма"], [], ["frontend"]),
    _s("jest", "Jest / Vitest", QA, ["jest", "vitest", "testing library", "react testing library"], ["test_automation", "javascript"], ["frontend"]),
    # Инфраструктура
    _s("linux", "Linux", INFRA, ["linux", "линукс", "unix", "ubuntu", "debian", "centos", "rhel"], ["linux"], ["devops", "backend"]),
    _s("docker", "Docker", INFRA, ["docker", "докер", "docker-compose", "docker compose", "контейнер"], ["containers"], ["devops", "backend"]),
    _s("kubernetes", "Kubernetes", INFRA, ["kubernetes", "k8s", "кубернетес", "openshift", "helm"], ["kubernetes"], ["devops"]),
    _s("terraform", "Terraform", INFRA, ["terraform", "iac", "infrastructure as code", "pulumi"], ["cicd"], ["devops"]),
    _s("ansible", "Ansible", INFRA, ["ansible", "chef", "puppet", "saltstack"], ["linux"], ["devops"]),
    _s("gitlab_ci", "GitLab CI / GitHub Actions", INFRA, ["gitlab ci", "gitlab-ci", "github actions", "ci/cd", "jenkins", "teamcity", "argo cd", "argocd"], ["cicd"], ["devops"]),
    _s("git", "Git", TOOLS, ["git", "github", "gitlab", "bitbucket"], ["cicd"], []),
    _s("nginx", "Nginx", INFRA, ["nginx", "haproxy", "envoy", "балансиров"], ["networks"], ["devops", "backend"]),
    _s("networks", "Сети TCP/IP", INFRA, ["tcp/ip", "tcp", "dns", "компьютерные сети", "сетевые протоколы", "сетевые технологии", "osi", "vpn", "iptables"], ["networks"], ["devops"]),
    _s("prometheus", "Prometheus / Grafana", INFRA, ["prometheus", "grafana", "мониторинг", "alertmanager", "victoriametrics", "zabbix"], ["observability"], ["devops"]),
    _s("elk", "ELK / логирование", INFRA, ["elk", "kibana", "logstash", "loki", "fluentd", "логирован"], ["observability"], ["devops"]),
    _s("sre", "SRE-практики", PRACT, ["sre", "slo", "sla", "sli", "error budget", "incident", "on-call", "postmortem"], ["observability"], ["devops"]),
    _s("cloud", "Облачные платформы", INFRA, ["aws", "gcp", "azure", "yandex cloud", "яндекс облако", "облачн", "vk cloud", "selectel"], ["containers"], ["devops"]),
    # Данные и ML
    _s("pandas", "pandas", DATA, ["pandas", "dataframe"], ["data_tools"], ["ml", "data_analyst"]),
    _s("numpy", "NumPy", DATA, ["numpy", "scipy"], ["data_tools"], ["ml"]),
    _s("scikit_learn", "scikit-learn", DATA, ["scikit-learn", "sklearn", "scikit learn"], ["ml"], ["ml"]),
    _s("gradient_boosting", "Градиентный бустинг", DATA, ["catboost", "xgboost", "lightgbm", "градиентный бустинг", "gradient boosting"], ["ml"], ["ml"]),
    _s("pytorch", "PyTorch", DATA, ["pytorch", "torch"], ["deep_learning"], ["ml"]),
    _s("tensorflow", "TensorFlow / Keras", DATA, ["tensorflow", "keras"], ["deep_learning"], ["ml"]),
    _s("nlp", "NLP", DATA, ["nlp", "обработка естественного языка", "transformers", "bert", "llm", "huggingface", "rag"], ["deep_learning", "ml"], ["ml"]),
    _s("cv", "Компьютерное зрение", DATA, ["computer vision", "компьютерное зрение", "opencv", "yolo", "cv-модел"], ["deep_learning"], ["ml"]),
    _s("mlops", "MLOps", DATA, ["mlops", "mlflow", "airflow", "kubeflow", "dvc", "feature store"], ["ml", "cicd"], ["ml"]),
    _s("statistics", "Статистика", DATA, ["статистик", "statistics", "теория вероятност", "матстат", "hypothesis testing", "проверка гипотез"], ["statistics"], ["ml", "data_analyst"]),
    _s("ab_testing", "A/B-тестирование", DATA, ["a/b", "ab-тест", "a/b-тест", "ab testing", "сплит-тест", "a/b тест"], ["analytics", "statistics"], ["data_analyst"]),
    _s("product_metrics", "Продуктовые метрики", DATA, ["продуктовые метрики", "retention", "ltv", "dau", "mau", "конверси", "юнит-экономик", "unit economics", "cohort", "когорт"], ["analytics"], ["data_analyst"]),
    _s("tableau", "BI (Tableau / Power BI / DataLens)", DATA, ["tableau", "power bi", "powerbi", "datalens", "superset", "metabase", "looker", "bi-систем"], ["analytics"], ["data_analyst"]),
    _s("excel", "Excel / Google Sheets", DATA, ["excel", "google sheets", "гугл таблиц", "vba"], ["analytics"], ["data_analyst"]),
    _s("spark", "Spark / Hadoop", DATA, ["spark", "pyspark", "hadoop", "hive"], ["data_tools"], ["ml", "data_analyst"]),
    _s("dwh", "DWH и ETL", DATA, ["dwh", "etl", "elt", "data warehouse", "хранилище данных", "dbt"], ["sql", "databases"], ["data_analyst"]),
    _s("visualization", "Визуализация данных", DATA, ["matplotlib", "seaborn", "plotly", "визуализац"], ["data_tools"], ["data_analyst", "ml"]),
    # Тестирование
    _s("test_design", "Тест-дизайн", QA, ["тест-дизайн", "тест дизайн", "test design", "граничные значения", "классы эквивалентности", "pairwise", "тест-кейс", "чек-лист", "test case"], ["testing_theory"], ["qa"]),
    _s("manual_testing", "Ручное тестирование", QA, ["ручное тестирование", "manual testing", "функциональное тестирование", "регрессионное тестирование", "регресс-тест"], ["testing_theory"], ["qa"]),
    _s("api_testing", "Тестирование API", QA, ["тестирование api", "api testing", "postman", "insomnia", "rest assured", "rest-assured"], ["http_api", "test_automation"], ["qa"]),
    _s("selenium", "Selenium / Playwright", QA, ["selenium", "playwright", "cypress", "selenide", "webdriver", "appium"], ["test_automation"], ["qa"]),
    _s("pytest", "pytest / JUnit / TestNG", QA, ["pytest", "junit", "testng", "unittest", "allure"], ["test_automation"], ["qa", "backend"]),
    _s("load_testing", "Нагрузочное тестирование", QA, ["нагрузочн", "jmeter", "locust", "k6", "gatling", "load testing"], ["test_automation"], ["qa"]),
    _s("jira", "Jira / TestIT / TestRail", TOOLS, ["jira", "confluence", "testrail", "testit", "test it", "youtrack", "qase"], ["testing_theory"], ["qa"]),
    _s("mobile_testing", "Тестирование мобильных приложений", QA, ["тестирование мобильн", "mobile testing", "appium"], ["testing_theory"], ["qa"]),
    # Практики
    _s("agile", "Agile / Scrum", PRACT, ["agile", "scrum", "kanban", "скрам", "канбан"], [], []),
    _s("tdd", "TDD / unit-тесты", PRACT, ["tdd", "unit-тест", "unit test", "юнит-тест", "модульные тест", "модульное тестир"], ["test_automation"], ["backend"]),
    _s("code_review", "Код-ревью", PRACT, ["код-ревью", "code review", "ревью кода"], [], []),
    _s("concurrency", "Многопоточность и конкурентность", PRACT, ["многопоточ", "concurrency", "multithreading", "goroutine", "горутин", "асинхронн"], ["architecture"], ["backend"]),
]

SKILL_BY_ID: dict[str, Skill] = {s.id: s for s in SKILLS}


_NO_NAME_MATCH = {"go", "c", "r_lang"}


def _compile(skill: Skill) -> re.Pattern:
    """Латинские синонимы ищем как отдельные токены (с учётом символов вроде c++, c#, .net),
    кириллические — как основу слова (префикс), чтобы ловить падежные формы: «микросервисами»."""
    parts = []
    # Однобуквенные/двухбуквенные имена (C, R, Go) слишком неоднозначны — ищем только по синонимам.
    names = skill.synonyms if skill.id in _NO_NAME_MATCH else (*skill.synonyms, skill.name)
    for syn in names:
        s = syn.lower().replace("ё", "е")
        if re.search(r"[а-я]", s):
            parts.append(rf"(?<![а-яa-z]){re.escape(s)}")
        else:
            parts.append(rf"(?<![a-z0-9+#]){re.escape(s)}(?![a-z0-9+#])")
    return re.compile("|".join(parts))


_COMPILED = [(s, _compile(s)) for s in SKILLS]
_GO_CONTEXT = re.compile(r"golang|backend|бэкенд|разработ|developer|микросерв|горутин|grpc")


def extract_skills(text: str, context: str | None = None) -> list[dict]:
    """Находит навыки в тексте. Возвращает [{id, name, count, first_pos}] по убыванию частоты.
    context — более широкий текст (вся вакансия) для разрешения неоднозначных упоминаний вроде «Go»."""
    if not text:
        return []
    low = text.lower().replace("ё", "е")
    found: dict[str, dict] = {}
    for skill, pat in _COMPILED:
        matches = list(pat.finditer(low))
        if skill.id == "go" and not matches and _GO_CONTEXT.search((context or text).lower()):
            # «go» как отдельное слово частотно в английском — учитываем только в ИТ-контексте
            matches = list(re.finditer(r"(?<![a-z])go(?![a-z])", low))
        if matches:
            found[skill.id] = {"id": skill.id, "name": skill.name, "count": len(matches), "first_pos": matches[0].start()}
    return sorted(found.values(), key=lambda x: (-x["count"], x["first_pos"]))


def skill_names(ids: list[str]) -> list[str]:
    return [SKILL_BY_ID[i].name if i in SKILL_BY_ID else i for i in ids]


def skills_for_spec(spec: str) -> list[Skill]:
    return [s for s in SKILLS if spec in s.specs]


def skill_domains(skill_id: str) -> tuple[str, ...]:
    s = SKILL_BY_ID.get(skill_id)
    return s.domains if s else ()
