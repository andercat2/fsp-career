# Нагрузочное тестирование

Стенд — `docker compose` на одной машине вместе с генератором нагрузки (Locust): AMD Ryzen 5 7500F 6-Core Processor; Docker — 12 vCPU, 15,5 ГБ; 700 кандидатов и 5 компаний демо-данных. Профиль ролей и сценарии — `loadtest/locustfile.py`, запуск — `python loadtest/run.py <сценарий>`, отчёт — `python loadtest/report.py`.

### load: до и после оптимизации

| Показатель | До | После |
|---|---|---|
| Запросов в секунду | 9,2 | 110,1 |
| p50 / p95 / p99, мс | 65 / 120 000 / 120 000 | 5 / 50 / 120 |
| Ошибок | 18,27% | 0,00% |
| `POST /employer/selections (NLP + подбор)`: p95, мс | 120 000 | 380 |
| `GET /employer/candidates (поиск)`: p95, мс | 120 000 | 190 |
| `GET /employer/selections/[id]`: p95, мс | 120 000 | 180 |
| `GET /vacancies`: p95, мс | 120 000 | 94 |
| `GET /employer/invitations`: p95, мс | 120 000 | 85 |
| `GET /employer/selections`: p95, мс | 120 000 | 84 |
| `GET /employer/dashboard`: p95, мс | 120 000 | 49 |
| `POST /testing/sessions/[token]/answer (full)`: p95, мс | 120 000 | 37 |

### steps: до и после оптимизации

| Показатель | До | После |
|---|---|---|
| Запросов в секунду | 24,1 | 173,1 |
| p50 / p95 / p99, мс | 9 / 120 000 / 120 000 | 6 / 490 / 910 |
| Ошибок | 6,92% | 0,00% |
| `POST /employer/selections (NLP + подбор)`: p95, мс | 120 000 | 1 600 |
| `GET /employer/candidates (поиск)`: p95, мс | 120 000 | 1 300 |
| `GET /employer/invitations`: p95, мс | 120 000 | 1 100 |
| `GET /vacancies`: p95, мс | 120 000 | 800 |
| `GET /employer/selections`: p95, мс | 120 000 | 710 |
| `GET /employer/candidates/[id]`: p95, мс | 120 000 | 640 |
| `GET /testing/eligibility`: p95, мс | 120 000 | 620 |
| `GET /candidate/dashboard`: p95, мс | 120 000 | 610 |

### load-after

Смешанная нагрузка: 300 одновременных пользователей всех ролей, 5 минут.

Запросов: 35 095, ошибок: 0 (0,00%), в среднем 110,1 запр/с; время ответа p50 / p95 / p99 — 5 / 50 / 120 мс.

| Запрос | Число | p50, мс | p95, мс | p99, мс | Ошибок |
|---|---|---|---|---|---|
| `POST /employer/selections (NLP + подбор)` | 178 | 180 | 380 | 600 | 0 |
| `GET /employer/candidates (поиск)` | 471 | 72 | 190 | 280 | 0 |
| `GET /employer/selections/[id]` | 493 | 69 | 180 | 270 | 0 |
| `GET /vacancies` | 907 | 34 | 94 | 150 | 0 |
| `GET /employer/invitations` | 334 | 8 | 85 | 130 | 0 |
| `GET /employer/selections` | 502 | 30 | 84 | 99 | 0 |
| `POST /auth/login` | 180 | 45 | 76 | 120 | 0 |
| `POST /testing/sessions (full)` | 154 | 14 | 59 | 83 | 0 |
| `GET /employer/dashboard` | 334 | 8 | 49 | 140 | 0 |
| `POST /testing/sessions/[token]/answer (full)` | 1967 | 12 | 37 | 75 | 0 |
| `GET /employer/candidates/[id]` | 222 | 13 | 35 | 56 | 0 |
| `POST /testing/sessions (express)` | 156 | 11 | 35 | 59 | 0 |

Пиковая загрузка контейнеров: frontend — CPU 16% (в среднем 9%), память 13 МБ; backend — CPU 95% (в среднем 58%), память 898 МБ; db — CPU 48% (в среднем 22%), память 139 МБ; mailpit — CPU 3% (в среднем 0%), память 8 МБ; sandbox — CPU 18% (в среднем 1%), память 18 МБ.

### load-before

Смешанная нагрузка: 300 одновременных пользователей всех ролей, 5 минут.

Запросов: 2 906, ошибок: 531 (18,27%), в среднем 9,2 запр/с; время ответа p50 / p95 / p99 — 65 / 120 000 / 120 000 мс.

| Запрос | Число | p50, мс | p95, мс | p99, мс | Ошибок |
|---|---|---|---|---|---|
| `GET /candidate/dashboard` | 99 | 210 | 120 000 | 120 000 | 33 |
| `GET /candidate/invitations` | 58 | 880 | 120 000 | 120 000 | 23 |
| `GET /candidate/profile` | 63 | 1 200 | 120 000 | 120 000 | 29 |
| `GET /candidate/resumes` | 53 | 110 | 120 000 | 120 000 | 22 |
| `GET /employer/candidates (поиск)` | 50 | 30 000 | 120 000 | 120 000 | 25 |
| `GET /employer/candidates/[id]` | 9 | 120 000 | 120 000 | 120 000 | 7 |
| `GET /employer/dashboard` | 42 | 60 000 | 120 000 | 120 000 | 21 |
| `GET /employer/invitations` | 31 | 940 | 120 000 | 120 000 | 11 |
| `GET /employer/selections` | 50 | 120 000 | 120 000 | 120 000 | 32 |
| `POST /employer/selections (NLP + подбор)` | 16 | 1 800 | 120 000 | 120 000 | 6 |
| `GET /employer/selections/[id]` | 16 | 750 | 120 000 | 120 000 | 2 |
| `GET /notifications` | 90 | 110 | 120 000 | 120 000 | 25 |

Пиковая загрузка контейнеров: frontend — CPU 10% (в среднем 1%), память 16 МБ; backend — CPU 238% (в среднем 22%), память 687 МБ; db — CPU 37% (в среднем 3%), память 102 МБ; mailpit — CPU 3% (в среднем 0%), память 8 МБ; sandbox — CPU 18% (в среднем 1%), память 23 МБ.

Ошибки: `/auth/login` — CatchResponseError('вход cand169@synthetic.example: 500') (1); `/employer/selections/[id]` — HTTPError('500 Server Error: Internal Server Error for url: /employer/selections/[id]') (1); `/auth/login` — CatchResponseError('вход cand167@synthetic.example: 500') (1); `/notifications` — HTTPError('504 Server Error: Gateway Time-out for url: /notifications') (25); `/testing/sessions/[token]/answer (full)` — CatchResponseError('ответ: 500 Internal Server Error') (26).

### exam-after

День тестирования: 300 кандидатов одновременно проходят тест, 6 минут.

Запросов: 20 400, ошибок: 0 (0,00%), в среднем 53,9 запр/с; время ответа p50 / p95 / p99 — 10 / 22 / 57 мс.

| Запрос | Число | p50, мс | p95, мс | p99, мс | Ошибок |
|---|---|---|---|---|---|
| `POST /auth/login` | 300 | 60 | 96 | 120 | 0 |
| `POST /testing/sessions (full)` | 644 | 12 | 46 | 56 | 0 |
| `GET /testing/eligibility` | 1492 | 7 | 40 | 52 | 0 |
| `POST /testing/sessions/[token]/answer (full)` | 8462 | 10 | 19 | 31 | 0 |
| `POST /testing/sessions (express)` | 848 | 10 | 16 | 28 | 0 |
| `POST /testing/sessions/[token]/answer (express)` | 6080 | 10 | 14 | 20 | 0 |
| `GET /testing/sessions/[token] (результат)` | 1287 | 6 | 10 | 12 | 0 |
| `GET /testing/history` | 1287 | 5 | 9 | 12 | 0 |

Пиковая загрузка контейнеров: frontend — CPU 6% (в среднем 3%), память 17 МБ; backend — CPU 110% (в среднем 36%), память 773 МБ; db — CPU 35% (в среднем 12%), память 163 МБ; mailpit — CPU 3% (в среднем 0%), память 8 МБ; sandbox — CPU 18% (в среднем 1%), память 26 МБ.

### steps-after

Ступенчатая нагрузка: +100 пользователей каждые 90 секунд до 800 — поиск предела.

Запросов: 128 097, ошибок: 0 (0,00%), в среднем 173,1 запр/с; время ответа p50 / p95 / p99 — 6 / 490 / 910 мс.

| Запрос | Число | p50, мс | p95, мс | p99, мс | Ошибок |
|---|---|---|---|---|---|
| `POST /employer/selections (NLP + подбор)` | 593 | 300 | 1 600 | 2 000 | 0 |
| `GET /employer/candidates (поиск)` | 1736 | 120 | 1 300 | 1 600 | 0 |
| `GET /employer/selections/[id]` | 1717 | 110 | 1 300 | 1 600 | 0 |
| `GET /employer/invitations` | 1193 | 55 | 1 100 | 1 500 | 0 |
| `GET /vacancies` | 3296 | 60 | 800 | 1 100 | 0 |
| `GET /employer/selections` | 1736 | 110 | 710 | 1 000 | 0 |
| `POST /testing/sessions (express)` | 1611 | 46 | 690 | 970 | 0 |
| `GET /employer/candidates/[id]` | 914 | 28 | 640 | 900 | 0 |
| `GET /testing/eligibility` | 3577 | 21 | 620 | 920 | 0 |
| `GET /candidate/dashboard` | 4832 | 17 | 610 | 880 | 0 |
| `POST /testing/sessions/[token]/answer (express)` | 4465 | 18 | 610 | 860 | 0 |
| `GET /employer/dashboard` | 1193 | 15 | 600 | 830 | 0 |

Пиковая загрузка контейнеров: frontend — CPU 32% (в среднем 15%), память 18 МБ; backend — CPU 275% (в среднем 107%), память 859 МБ; db — CPU 177% (в среднем 48%), память 283 МБ; mailpit — CPU 4% (в среднем 0%), память 8 МБ; sandbox — CPU 20% (в среднем 1%), память 18 МБ.

| Пользователей | Запр/с | p95, мс | Ошибок/с |
|---|---|---|---|
| 100 | 56,9 | 59 | 0,00 |
| 200 | 81,8 | 64 | 0,00 |
| 300 | 120,3 | 59 | 0,00 |
| 400 | 159,0 | 59 | 0,00 |
| 500 | 202,5 | 63 | 0,00 |
| 600 | 239,3 | 67 | 0,00 |
| 700 | 274,6 | 100 | 0,00 |
| 800 | 292,1 | 390 | 0,00 |

### steps-before

Ступенчатая нагрузка: +100 пользователей каждые 90 секунд до 600 — поиск предела.

Запросов: 13 493, ошибок: 934 (6,92%), в среднем 24,1 запр/с; время ответа p50 / p95 / p99 — 9 / 120 000 / 120 000 мс.

| Запрос | Число | p50, мс | p95, мс | p99, мс | Ошибок |
|---|---|---|---|---|---|
| `POST /auth/login` | 310 | 900 | 120 000 | 120 000 | 143 |
| `GET /candidate/dashboard` | 484 | 17 | 120 000 | 120 000 | 47 |
| `GET /candidate/invitations` | 310 | 13 | 120 000 | 120 000 | 38 |
| `GET /candidate/profile` | 330 | 13 | 120 000 | 120 000 | 38 |
| `GET /candidate/resumes` | 319 | 10 | 120 000 | 120 000 | 29 |
| `GET /employer/candidates (поиск)` | 181 | 190 | 120 000 | 120 000 | 42 |
| `GET /employer/candidates/[id]` | 82 | 27 | 120 000 | 120 000 | 13 |
| `GET /employer/dashboard` | 163 | 140 | 120 000 | 120 000 | 36 |
| `GET /employer/invitations` | 149 | 61 | 120 000 | 120 000 | 24 |
| `GET /employer/selections` | 190 | 80 | 120 000 | 120 000 | 39 |
| `POST /employer/selections (NLP + подбор)` | 80 | 340 | 120 000 | 120 000 | 16 |
| `GET /notifications` | 467 | 8 | 120 000 | 120 000 | 34 |

Пиковая загрузка контейнеров: frontend — CPU 14% (в среднем 2%), память 21 МБ; backend — CPU 257% (в среднем 28%), память 629 МБ; db — CPU 48% (в среднем 7%), память 114 МБ; mailpit — CPU 4% (в среднем 0%), память 8 МБ; sandbox — CPU 20% (в среднем 1%), память 18 МБ.

Ошибки: `/auth/login` — CatchResponseError('вход cand260@synthetic.example: 504') (1); `/auth/login` — CatchResponseError('вход cand235@synthetic.example: 504') (1); `/auth/login` — CatchResponseError('вход cand196@synthetic.example: 504') (1); `/auth/login` — CatchResponseError('вход cand233@synthetic.example: 504') (1); `/auth/login` — CatchResponseError('вход cand281@synthetic.example: 504') (1).

| Пользователей | Запр/с | p95, мс | Ошибок/с |
|---|---|---|---|
| 100 | 40,2 | 140 | 0,00 |
| 200 | 78,4 | 160 | 0,00 |
| 300 | 19,0 | 260 | 0,41 |
| 400 | 6,6 | 490 | 4,91 |
| 500 | 4,6 | 1 200 | 3,66 |
| 600 | 5,4 | 120 000 | 3,27 |
