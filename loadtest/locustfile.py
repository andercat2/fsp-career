"""Нагрузочный тест «ФСП Карьера» (Locust).

Профиль нагрузки — смесь ролей, близкая к реальной работе платформы:
  Visitor    — посетители без входа: главная (SPA, бандл, статистика, методика, справочники);
  Candidate  — кандидаты в кабинете: сводка, уведомления, профиль, резюме, приглашения, вакансии с оценкой совпадения;
  TestTaker  — кандидаты, проходящие тест: полный адаптивный тест (если уровень доступен) или экспресс-тест, ответ
               на каждое задание с паузой «на обдумывание», затем страница результата;
  Employer   — работодатели: подборки, поиск по банку с фильтрами, карточки кандидатов, новая подборка по тексту.

Учётные записи — демо-данные стенда: 700 синтетических кандидатов (cand000…cand699@synthetic.example) и 5 компаний,
пароль demo12345. Каждый виртуальный кандидат входит под своей записью; «сотрудники» одной компании делят её токен
(лимит входа — 8 попыток за 5 минут на адрес). Пауза между ответами сжата до 3–10 секунд: один виртуальный кандидат
отвечает в несколько раз чаще живого.

Профиль «ступени» (LOAD_SHAPE=steps) повышает число пользователей ступенями, чтобы найти предел производительности.
Запуск и сценарии — loadtest/README.md, сводный прогон — python loadtest/run.py.
"""
from __future__ import annotations

import http.client
import itertools
import os
import random
import re

from gevent.lock import Semaphore
from locust import HttpUser, LoadTestShape, between, task
from locust.exception import StopUser
from urllib3.connection import HTTPConnection


def _send_headers_with_body() -> None:
    """Заголовки и небольшое тело запроса уходят в сокет одной записью, как у браузера (Chromium объединяет их до
    1400 байт). urllib3 пишет их двумя вызовами, и проброс портов Docker Desktop задерживает второй сегмент до
    подтверждения первого (алгоритм Нейгла и отложенный ACK): каждый POST получал ≈ 42 мс, которых нет ни у браузера,
    ни на Linux-сервере. Пустой POST: 44 мс из requests, 3,5 мс из curl."""
    send, send_output, getresponse = http.client.HTTPConnection.send, http.client.HTTPConnection._send_output, \
        HTTPConnection.getresponse

    def _send_output(self, message_body=None, encode_chunked=False):
        if message_body is not None:
            return send_output(self, message_body, encode_chunked)
        self._buffer.extend((b"", b""))
        self._lt_headers = b"\r\n".join(self._buffer)
        del self._buffer[:]

    def _flush(self, body: bytes | None = None) -> bytes | None:
        head, self._lt_headers = getattr(self, "_lt_headers", None), None
        if head is None:
            return body
        if isinstance(body, (bytes, bytearray)) and len(head) + len(body) <= 1400:
            return head + body
        send(self, head)
        return body

    HTTPConnection._send_output = _send_output
    HTTPConnection.send = lambda self, data: send(self, _flush(self, data))
    HTTPConnection.getresponse = lambda self, *a, **kw: (_flush(self), getresponse(self, *a, **kw))[1]


_send_headers_with_body()

API = "/api/v1"
PASSWORD = "demo12345"
N_CANDIDATES = 700
COMPANIES = ["employer@demo.ru", "hr@fintechlab.example", "jobs@pixel-games.example", "career@medtech.example",
             "it@logplus.example"]
NEEDS = [
    ("Python-разработчик", "Ищем Python-разработчика уровня Middle в команду платежей: FastAPI, PostgreSQL, Docker, "
                           "REST API. Будет плюсом Kafka. Зарплата 250 000 – 320 000 руб., гибрид, Москва."),
    ("QA-инженер", "Нужен QA-инженер Junior: тест-дизайн, Postman, SQL, Jira. 90–120 тыс. руб., офис в Казани."),
    ("DevOps-инженер", "DevOps / SRE уровня Middle+: Kubernetes, Terraform, Prometheus, GitLab CI. Удалённо, "
                       "до 380 000 руб."),
    ("Frontend-разработчик", "Frontend-разработчик Middle: React, TypeScript, Vite, тесты на Jest. 200–260 тыс., "
                             "гибрид, Санкт-Петербург."),
    ("Аналитик данных", "Продуктовый аналитик: SQL, A/B-тесты, Python (pandas), BI-дашборды. Junior или Middle, "
                        "150–220 тыс. руб."),
]
SEARCHES = [
    {"specialization": "backend", "grades": "middle,senior", "skills": "python"},
    {"specialization": "frontend", "sort": "fresh"},
    {"specialization": "devops", "has_fsp": "true"},
    {"specialization": "qa", "grades": "junior"},
    {"specialization": "data_analyst", "sort": "salary"},
    {"skills": "postgresql,docker", "verified_only": "true"},
]

_next_candidate = itertools.count(int(os.environ.get("CANDIDATE_OFFSET", "0")))
_company_tokens: dict[str, str] = {}
_company_lock = Semaphore()


def _login(user: HttpUser, email: str) -> str:
    with user.client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD}, name="/auth/login",
                          catch_response=True) as r:
        if r.status_code != 200:
            r.failure(f"вход {email}: {r.status_code}")
            raise StopUser()
        return r.json()["access_token"]


class Authed(HttpUser):
    abstract = True
    headers: dict[str, str] = {}

    def get(self, path: str, name: str | None = None, **kw):
        return self.client.get(API + path, headers=self.headers, name=name or path, **kw)

    def post(self, path: str, body: dict | None = None, name: str | None = None, **kw):
        return self.client.post(API + path, json=body, headers=self.headers, name=name or path, **kw)


class Visitor(HttpUser):
    """Посетитель главной без входа: страница, бандл, статистика, методика, справочники."""
    weight = 3
    wait_time = between(3, 8)
    assets: list[str] = []

    def on_start(self):
        r = self.client.get("/", name="/ (SPA)")
        self.assets = re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', r.text)[:2]

    @task(4)
    def landing(self):
        self.client.get("/", name="/ (SPA)")
        for a in self.assets:
            self.client.get(a, name="/assets/* (бандл)")
        self.client.get(f"{API}/public/stats", name="/public/stats")
        self.client.get(f"{API}/public/methodology", name="/public/methodology")
        self.client.get(f"{API}/reference", name="/reference")

    @task(1)
    def methodology_page(self):
        self.client.get("/methodology", name="/ (SPA)")
        self.client.get(f"{API}/public/methodology", name="/public/methodology")


class Candidate(Authed):
    """Кандидат в личном кабинете."""
    weight = 4
    wait_time = between(3, 10)

    def on_start(self):
        self.email = f"cand{next(_next_candidate) % N_CANDIDATES:03d}@synthetic.example"
        self.headers = {"Authorization": f"Bearer {_login(self, self.email)}"}
        self.get("/auth/me")

    @task(3)
    def dashboard(self):
        self.get("/candidate/dashboard")
        self.get("/notifications")

    @task(2)
    def profile(self):
        self.get("/candidate/profile")
        self.get("/candidate/resumes")

    @task(2)
    def invitations(self):
        self.get("/candidate/invitations")

    @task(2)
    def vacancies(self):
        r = self.get("/vacancies")
        if r.ok and r.json():
            self.get(f"/vacancies/{random.choice(r.json())['id']}", name="/vacancies/[id]")

    @task(1)
    def grade(self):
        self.get("/testing/eligibility")
        self.get("/testing/history")


def _answer_for(q: dict):
    """Правдоподобный ответ: вариант из предложенных, число или строка — правильность для нагрузки не важна."""
    kind = q.get("kind")
    if kind == "single":
        return random.choice(q["options"])["id"]
    if kind == "multi":
        return [o["id"] for o in random.sample(q["options"], k=random.randint(1, 2))]
    if kind == "numeric":
        return str(random.randint(0, 50))
    return random.choice(["SELECT", "200", "O(n)", "None", "True", "git rebase"])


class TestTaker(Authed):
    """Кандидат, проходящий тест: полный (если уровень доступен) или экспресс."""
    weight = 3
    wait_time = between(5, 15)
    think = (3.0, 10.0)

    def on_start(self):
        self.email = f"cand{next(_next_candidate) % N_CANDIDATES:03d}@synthetic.example"
        self.headers = {"Authorization": f"Bearer {_login(self, self.email)}"}

    @task
    def take_test(self):
        el = self.get("/testing/eligibility")
        if not el.ok or not el.json().get("ready"):
            return
        allowed = [g["grade"] for g in el.json()["grades"] if g["allowed"]]
        mode, grade = ("full", random.choice(allowed)) if allowed else ("express", "middle")
        with self.post("/testing/sessions", {"grade": grade, "mode": mode}, name=f"/testing/sessions ({mode})",
                       catch_response=True) as r:
            if r.status_code == 429:  # лимит экспресс-тестов на сутки исчерпан — это не ошибка нагрузки
                r.success()
                return
            if not r.ok:
                r.failure(f"старт теста: {r.status_code} {r.text[:120]}")
                return
            view = r.json()
        token = view["token"]
        for _ in range(40):
            if view.get("status") != "in_progress" or not view.get("question"):
                break
            self.wait_seconds(*self.think)
            q = view["question"]
            with self.post(f"/testing/sessions/{token}/answer", {"response_id": q["id"], "answer": _answer_for(q)},
                           name=f"/testing/sessions/[token]/answer ({mode})", catch_response=True) as a:
                if not a.ok:
                    a.failure(f"ответ: {a.status_code} {a.text[:120]}")
                    return
                view = a.json()
        self.get(f"/testing/sessions/{token}", name="/testing/sessions/[token] (результат)")
        self.get("/testing/history")

    def wait_seconds(self, lo: float, hi: float) -> None:
        import gevent

        gevent.sleep(random.uniform(lo, hi))


class Employer(Authed):
    """Работодатель: подборки, поиск по банку, карточки кандидатов, новая подборка по тексту потребности."""
    weight = 2
    wait_time = between(4, 12)
    candidate_ids: list[int] = []

    def on_start(self):
        email = random.choice(COMPANIES)
        with _company_lock:
            if email not in _company_tokens:
                _company_tokens[email] = _login(self, email)
        self.headers = {"Authorization": f"Bearer {_company_tokens[email]}"}
        self.selections: list[int] = []

    @task(2)
    def dashboard(self):
        self.get("/employer/dashboard")
        self.get("/employer/invitations")

    @task(3)
    def selections_view(self):
        r = self.get("/employer/selections")
        if r.ok and r.json():
            sid = random.choice(r.json())["id"]
            params = random.choice([{}, {"grades": "middle"}, {"verified_only": "true"}, {"page": 2}])
            self.get(f"/employer/selections/{sid}", name="/employer/selections/[id]", params=params)

    @task(3)
    def search(self):
        r = self.get("/employer/candidates", name="/employer/candidates (поиск)", params=random.choice(SEARCHES))
        if r.ok:
            self.candidate_ids = [x["id"] for x in r.json().get("results", [])][:20]

    @task(2)
    def candidate_card(self):
        if self.candidate_ids:
            self.get(f"/employer/candidates/{random.choice(self.candidate_ids)}", name="/employer/candidates/[id]")

    @task(1)
    def new_selection(self):
        title, text = random.choice(NEEDS)
        self.post("/employer/selections", {"title": title, "text": text}, name="/employer/selections (NLP + подбор)")


if os.environ.get("LOAD_SHAPE") == "steps":  # объявленный профиль Locust применяет всегда — только по запросу

    class Steps(LoadTestShape):
        """Ступенчатая нагрузка: +STEP_USERS пользователей каждые STEP_SECONDS секунд до MAX_USERS."""
        step_users = int(os.environ.get("STEP_USERS", "100"))
        step_seconds = int(os.environ.get("STEP_SECONDS", "90"))
        max_users = int(os.environ.get("MAX_USERS", "600"))

        def tick(self):
            n = (int(self.get_run_time() // self.step_seconds) + 1) * self.step_users
            return None if n > self.max_users else (n, self.step_users / 10)
