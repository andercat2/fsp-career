"""Инфраструктурные домены: Linux, сети, контейнеры, Kubernetes, CI/CD и Git, мониторинг и SRE."""
from __future__ import annotations

import ipaddress
import math
import random
from collections import Counter

from app.services.testing.bank.core import Rendered, family, mcq, multi, options_from

# =============================== Linux ===============================
L = "linux"


def _perm_str(octal: str) -> str:
    out = ""
    for ch in octal:
        v = int(ch)
        out += ("r" if v & 4 else "-") + ("w" if v & 2 else "-") + ("x" if v & 1 else "-")
    return out


@family("linux.chmod", L, 2, "input", "Права доступа", time_limit=90)
def linux_chmod(rng: random.Random, _l):
    octal = "".join(rng.choice("01234567"[4:] if i == 0 else "01234567") for i in range(3))
    if rng.random() < 0.5:
        return Rendered(f"Права файла: `{_perm_str(octal)}`. Какой восьмеричный код передать в `chmod`, чтобы их установить?",
                        "input", octal, norm="exact", placeholder="например: 644")
    return Rendered(f"Выполнено `chmod {octal} file`. Как права будут показаны в `ls -l` (9 символов без типа файла)?",
                    "input", _perm_str(octal), norm="exact", placeholder="например: rw-r--r--")


@family("linux.pipeline", L, 3, "input", "Конвейеры shell", time_limit=180)
def linux_pipeline(rng: random.Random, _l):
    while True:  # для варианта с самым частым IP ответ должен быть однозначным
        ips = [f"10.0.0.{rng.randint(1, 6)}" for _ in range(10)]
        top_counts = Counter(ips).most_common(2)
        if len(top_counts) == 1 or top_counts[0][1] > top_counts[1][1]:
            break
    codes = [rng.choice([200, 200, 200, 404, 500, 301]) for _ in range(10)]
    sizes = [rng.randint(1, 9) * 100 for _ in range(10)]
    log = "\n".join(f"{ip} GET /p{rng.randint(1, 4)} {c} {s}" for ip, c, s in zip(ips, codes, sizes, strict=True))
    variant = rng.randrange(3)
    if variant == 0:
        cmd = "awk '{print $1}' access.log | sort | uniq | wc -l"
        ans = str(len(set(ips)))
    elif variant == 1:
        code = rng.choice(sorted(set(codes)))
        cmd = f"awk '$4 == {code} {{s += $5}} END {{print s}}' access.log"
        ans = str(sum(s for c, s in zip(codes, sizes, strict=True) if c == code))
    else:
        ip_top, top = Counter(ips).most_common(1)[0]
        cmd = "awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -1"
        ans = f"{top} {ip_top}"
    return Rendered(f"Файл `access.log` (поля: ip, метод, путь, код, размер):\n\n```\n{log}\n```\n\nЧто выведет команда?",
                    "input", ans, code=cmd, code_lang="bash")


@family("linux.cron", L, 3, "numeric", "Расписания cron", time_limit=150)
def linux_cron(rng: random.Random, _l):
    m_step = rng.choice([None, 5, 10, 15, 20, 30])
    minute = "0" if m_step is None else f"*/{m_step}"
    per_hour = 1 if m_step is None else 60 // m_step
    h_from, h_to = rng.choice([(9, 17), (8, 20), (0, 23), (10, 18)])
    hours = h_to - h_from + 1
    dow, days = rng.choice([("1-5", 5), ("*", 7), ("6,0", 2)])
    expr = f"{minute} {h_from}-{h_to} * * {dow}"
    return Rendered(f"Сколько раз за неделю выполнится задание с расписанием `{expr}`?", "numeric", per_hour * hours * days)


mcq("linux.sigkill", L, 2, "Чем SIGTERM отличается от SIGKILL?", "SIGTERM можно перехватить и корректно завершиться, "
    "SIGKILL — нет", ["Ничем", "SIGKILL можно перехватить", "SIGTERM останавливает процесс на паузу",
                      "SIGKILL перезапускает процесс"], topic="Сигналы")
mcq("linux.hardlink", L, 3, "Что произойдёт с жёсткой ссылкой, если удалить исходный файл?",
    "Данные останутся доступны по жёсткой ссылке", ["Ссылка станет «битой»", "Удалится и ссылка",
                                                    "Ссылка превратится в символическую", "Файловая система вернёт ошибку"],
    topic="Ссылки")
mcq("linux.redirect", L, 4, "Куда попадёт stderr в команде `cmd 2>&1 > out.txt`?",
    "В терминал (stdout на момент перенаправления), а stdout — в out.txt", ["Оба потока в out.txt",
                                                                             "stderr в out.txt, stdout в терминал",
                                                                             "В /dev/null", "Команда завершится ошибкой"],
    topic="Перенаправление потоков")
mcq("linux.inodes", L, 5, "`df -h` показывает 40% свободного места, но создать файл не удаётся: «No space left on device». "
    "Вероятная причина?", "Закончились inode'ы (`df -i`)", ["Сломан диск", "Не хватает RAM",
                                                            "Слишком длинное имя файла", "Файловая система только для чтения"],
    topic="Файловые системы")
mcq("linux.load_avg", L, 4, "На сервере 4 ядра, load average = 8.0. Что это значит?",
    "В среднем процессов, готовых к выполнению или ждущих I/O, вдвое больше, чем ядер", ["CPU загружен на 8%",
                                                                                           "Свободно 8 ГБ памяти",
                                                                                           "Запущено 8 процессов",
                                                                                           "Всё в норме, это 200% нормы"],
    topic="Нагрузка")
mcq("linux.systemctl", L, 2, "Чем `systemctl enable` отличается от `systemctl start`?",
    "enable включает автозапуск при загрузке, start запускает сервис сейчас", ["Ничем", "start включает автозапуск",
                                                                                "enable перезапускает сервис",
                                                                                "enable удаляет юнит"], topic="systemd")
mcq("linux.ssh_keys", L, 1, "Какой файл на сервере содержит открытые ключи, разрешённые для входа по SSH?",
    "`~/.ssh/authorized_keys`", ["`~/.ssh/id_rsa`", "`/etc/passwd`", "`~/.ssh/known_hosts`", "`/etc/shadow`"],
    topic="SSH")
mcq("linux.find_mtime", L, 3, "Какая команда найдёт файлы в /var/log, изменённые более 7 дней назад?",
    "`find /var/log -type f -mtime +7`", ["`find /var/log -mtime -7`", "`ls -t /var/log | tail -7`",
                                          "`grep -r 7 /var/log`", "`find /var/log -size +7`"], topic="find")

# =============================== Сети ===============================
N = "networks"


@family("net.cidr_hosts", N, 2, "numeric", "Адресация CIDR", time_limit=90)
def net_cidr_hosts(rng: random.Random, _l):
    n = rng.randint(22, 29)
    return Rendered(f"Сколько адресов можно назначить хостам в подсети `/{n}` (без адреса сети и широковещательного)?",
                    "numeric", 2 ** (32 - n) - 2)


@family("net.mask", N, 2, "input", "Маски подсети", time_limit=90)
def net_mask(rng: random.Random, _l):
    n = rng.randint(17, 30)
    return Rendered(f"Запишите маску подсети `/{n}` в десятичном виде.", "input",
                    str(ipaddress.IPv4Network(f"0.0.0.0/{n}").netmask), norm="exact", placeholder="255.255.255.0")


@family("net.in_subnet", N, 3, "single", "Принадлежность подсети", time_limit=150)
def net_in_subnet(rng: random.Random, _l):
    n = rng.choice([20, 22, 26, 27, 28])
    base = ipaddress.IPv4Address(f"10.{rng.randint(0, 50)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}")
    net = ipaddress.IPv4Network(f"{base}/{n}", strict=False)
    inside = net.network_address + rng.randint(1, net.num_addresses - 2)
    outs = set()
    while len(outs) < 4:
        delta = rng.choice([-1, 1]) * rng.randint(1, 3) * net.num_addresses + rng.randint(0, net.num_addresses - 1)
        cand = ipaddress.IPv4Address(int(net.network_address) + delta)
        if cand not in net:
            outs.add(str(cand))
    opts, key = options_from(rng, str(inside), list(outs))
    return Rendered(f"Какой адрес принадлежит подсети `{net}`?", "single", key, options=opts)


@family("net.ports", N, 1, "single", "Стандартные порты", time_limit=60)
def net_ports(rng: random.Random, _l):
    ports = {"SSH": 22, "DNS": 53, "HTTPS": 443, "PostgreSQL": 5432, "Redis": 6379, "SMTP": 25, "HTTP": 80, "MySQL": 3306}
    svc = rng.choice(list(ports))
    opts, key = options_from(rng, ports[svc], [p for s, p in ports.items() if s != svc])
    return Rendered(f"Какой порт по умолчанию использует **{svc}**?", "single", key, options=opts)


mcq("net.tcp_udp", N, 1, "Чем UDP отличается от TCP?", "UDP не устанавливает соединение и не гарантирует доставку и порядок",
    ["UDP надёжнее TCP", "UDP работает только в локальной сети", "UDP шифрует данные", "UDP медленнее из-за подтверждений"],
    topic="Транспортный уровень")
mcq("net.handshake", N, 2, "Какая последовательность пакетов устанавливает TCP-соединение?", "SYN → SYN-ACK → ACK",
    ["ACK → SYN → FIN", "SYN → ACK", "HELLO → OK", "SYN → FIN → ACK"], topic="TCP")
mcq("net.cname", N, 2, "Для чего нужна DNS-запись CNAME?", "Задать псевдоним одного доменного имени для другого",
    ["Указать почтовый сервер", "Указать IPv6-адрес", "Подтвердить владение доменом", "Задать обратную зону"], topic="DNS")
mcq("net.l4_l7", N, 4, "Что умеет L7-балансировщик в отличие от L4?", "Маршрутизировать по содержимому HTTP: пути, заголовкам, cookie",
    ["Работать с TCP", "Распределять по IP", "Использовать round-robin", "Работать без DNS"], topic="Балансировка")
mcq("net.time_wait", N, 5, "Почему на нагруженном клиенте накапливаются сокеты в состоянии TIME_WAIT?",
    "Сторона, инициировавшая закрытие, удерживает соединение 2·MSL, чтобы корректно обработать запоздавшие пакеты",
    ["Из-за утечки памяти в ядре", "Сервер не отвечает на SYN", "Из-за DNS-кэша", "Из-за HTTPS"], topic="TCP")
mcq("net.nat", N, 3, "Что делает NAT на домашнем маршрутизаторе?", "Подменяет внутренние адреса и порты на внешний адрес",
    ["Шифрует трафик", "Раздаёт DNS-имена", "Ускоряет Wi-Fi", "Блокирует все входящие соединения по определению"],
    topic="NAT")
mcq("net.traceroute", N, 4, "На чём основана работа traceroute?", "На увеличении TTL и ICMP-сообщениях Time Exceeded от маршрутизаторов",
    ["На DNS-запросах", "На ARP-таблицах", "На HTTP-редиректах", "На широковещательных пакетах"], topic="Диагностика")
mcq("net.tls", N, 3, "Что проверяет клиент при TLS-рукопожатии, чтобы убедиться в подлинности сервера?",
    "Цепочку сертификатов до доверенного корневого ЦС и совпадение имени хоста", ["IP-адрес клиента",
                                                                                  "Наличие cookie", "Версию HTTP",
                                                                                  "Скорость соединения"], topic="TLS")

# =============================== Контейнеры ===============================
C = "containers"


@family("docker.cache", C, 3, "numeric", "Кэш слоёв Docker", time_limit=150)
def docker_cache(rng: random.Random, _l):
    stack = rng.choice(["python", "node"])
    if stack == "python":
        lines = ["FROM python:3.12-slim", "WORKDIR /app", "COPY requirements.txt .", "RUN pip install -r requirements.txt",
                 "COPY . .", "RUN python -m compileall .", 'CMD ["python", "main.py"]']
        changed = rng.choice([("requirements.txt", 3), ("main.py", 5)])
    else:
        lines = ["FROM node:22-alpine", "WORKDIR /app", "COPY package.json package-lock.json ./", "RUN npm ci",
                 "COPY . .", "RUN npm run build", 'CMD ["node", "dist/index.js"]']
        changed = rng.choice([("package-lock.json", 3), ("src/index.ts", 5)])
    code = "\n".join(f"{i + 1:>2}  {ln}" for i, ln in enumerate(lines))
    return Rendered(f"Образ собирался ранее, кэш есть. Изменён только файл `{changed[0]}`. Начиная с какой строки "
                    "инструкции будут выполняться заново (кэш инвалидирован)?", "numeric", changed[1], code=code,
                    code_lang="dockerfile")


mcq("docker.cmd_entry", C, 3, "Как связаны ENTRYPOINT и CMD в exec-форме?", "CMD передаётся аргументами к ENTRYPOINT "
    "и легко переопределяется при `docker run`", ["Они взаимоисключающие", "CMD всегда выполняется до ENTRYPOINT",
                                                  "ENTRYPOINT игнорируется, если есть CMD", "Это синонимы"],
    topic="Dockerfile")
mcq("docker.multistage", C, 3, "Зачем нужна многоэтапная (multi-stage) сборка?", "Собрать в одном образе, а в финальный "
    "скопировать только артефакты, уменьшив размер и поверхность атаки", ["Для параллельного запуска контейнеров",
                                                                         "Для шифрования слоёв", "Для обновления ОС хоста",
                                                                         "Для поддержки Windows"], topic="Dockerfile")
mcq("docker.volume", C, 2, "Как сохранить данные БД при пересоздании контейнера?", "Хранить их в именованном томе (volume)",
    ["Сделать docker commit", "Увеличить размер образа", "Использовать ENTRYPOINT", "Перезапускать контейнер с --rm"],
    topic="Тома")
mcq("docker.image_container", C, 1, "Чем образ отличается от контейнера?", "Образ — неизменяемый шаблон, контейнер — "
    "запущенный экземпляр с собственным слоем записи", ["Ничем", "Контейнер хранится в реестре", "Образ — это процесс",
                                                        "Контейнер нельзя остановить"], topic="Основы")
mcq("docker.compose_dns", C, 3, "Как сервис `api` в docker compose обращается к сервису `db` в той же сети?",
    "По имени сервиса: `db:5432`", ["По `localhost:5432`", "Только по IP хоста", "Через `host.docker.internal` всегда",
                                    "Через публикацию порта на хост"], topic="Сети Docker")
mcq("docker.expose", C, 4, "Что делает инструкция EXPOSE 8080 в Dockerfile?", "Документирует порт; публикация на хост "
    "требует `-p` при запуске", ["Публикует порт на хосте", "Открывает порт в фаерволе", "Запускает сервер на 8080",
                                 "Запрещает другие порты"], topic="Dockerfile")
mcq("docker.pid1", C, 5, "Почему приложение в контейнере может не завершаться корректно по `docker stop`?",
    "Процесс с PID 1 не получает/не обрабатывает SIGTERM (например, запущен через shell-форму CMD)",
    ["Docker не отправляет сигналы", "Не хватает памяти", "Из-за EXPOSE", "Из-за многоэтапной сборки"], topic="Сигналы")
mcq("docker.isolation", C, 4, "Какие механизмы ядра Linux обеспечивают изоляцию контейнеров?",
    "Namespaces и cgroups", ["Виртуализация CPU (VT-x)", "SELinux и только он", "chroot и cron", "iptables и systemd"],
    topic="Изоляция")

# =============================== Kubernetes ===============================
K = "kubernetes"


@family("k8s.rolling", K, 4, "numeric", "Rolling update", time_limit=150)
def k8s_rolling(rng: random.Random, _l):
    n = rng.choice([4, 6, 8, 10, 12])
    surge, unav = rng.choice([25, 50]), rng.choice([0, 25])
    if rng.random() < 0.5:
        ans = n + math.ceil(n * surge / 100)
        q = "Какое максимальное число подов может существовать одновременно во время обновления?"
    else:
        ans = n - math.floor(n * unav / 100)
        q = "Какое минимальное число доступных подов гарантируется во время обновления?"
    return Rendered(f"Deployment: `replicas: {n}`, стратегия RollingUpdate с `maxSurge: {surge}%`, "
                    f"`maxUnavailable: {unav}%`. {q}", "numeric", ans,
                    explanation="maxSurge округляется вверх, maxUnavailable — вниз.")


@family("k8s.requests", K, 3, "numeric", "Requests и планирование", time_limit=120)
def k8s_requests(rng: random.Random, _l):
    alloc = rng.choice([3800, 3900, 7800, 1900])
    req = rng.choice([250, 300, 500, 750])
    return Rendered(f"На узле allocatable CPU = {alloc}m, других подов нет. Под запрашивает `requests.cpu: {req}m` "
                    f"(limit — {req * 2}m). Сколько таких подов планировщик разместит на узле по CPU?", "numeric",
                    alloc // req, explanation="Планировщик учитывает requests, а не limits.")


mcq("k8s.readiness", K, 3, "Чем readinessProbe отличается от livenessProbe?", "readiness исключает под из балансировки, "
    "liveness перезапускает контейнер", ["Ничем", "readiness перезапускает под", "liveness управляет масштабированием",
                                         "readiness проверяет только при старте узла"], topic="Пробы")
mcq("k8s.statefulset", K, 4, "Когда нужен StatefulSet вместо Deployment?", "Когда подам нужны стабильные имена и "
    "собственные постоянные тома (БД, брокеры)", ["Для stateless API", "Для CronJob", "Для ускорения деплоя",
                                                  "Когда нужен один под"], topic="Контроллеры")
mcq("k8s.service_types", K, 2, "Какой тип Service делает приложение доступным только внутри кластера?", "ClusterIP",
    ["NodePort", "LoadBalancer", "ExternalName", "Ingress"], topic="Service")
mcq("k8s.secret", K, 2, "Чем Secret отличается от ConfigMap по умолчанию?", "Значения кодируются base64 и могут "
    "шифроваться в etcd при настройке; по сути это не шифрование", ["Secret всегда зашифрован ключом пользователя",
                                                                    "ConfigMap нельзя монтировать как файл",
                                                                    "Secret хранится только на узле", "Ничем"],
    topic="Конфигурация")
mcq("k8s.oom", K, 3, "Под перезапускается со статусом OOMKilled. Что это значит?", "Контейнер превысил limit по памяти",
    ["Не хватило CPU", "Образ не найден", "Провалилась readinessProbe", "Узел перезагружен"], topic="Ресурсы")
mcq("k8s.hpa", K, 3, "На основании чего HorizontalPodAutoscaler по умолчанию масштабирует Deployment?",
    "Средней утилизации CPU относительно requests", ["Числа узлов", "Размера образа", "Количества логов",
                                                     "Времени суток"], topic="Автомасштабирование")
mcq("k8s.taints", K, 5, "Для чего используют taints на узлах?", "Чтобы на узел планировались только поды с "
    "соответствующими tolerations", ["Для маркировки подов", "Для ограничения памяти", "Для сетевых политик",
                                     "Для хранения секретов"], topic="Планирование")
mcq("k8s.pdb", K, 5, "Что гарантирует PodDisruptionBudget?", "Минимальное число доступных подов при добровольных "
    "прерываниях (drain узла, обновление)", ["Защиту от OOM", "Бюджет на облако", "Лимит CPU", "Порядок запуска подов"],
    topic="Надёжность")
mcq("k8s.ingress", K, 3, "Что делает Ingress?", "Описывает HTTP-маршрутизацию внешнего трафика к сервисам по хостам и путям",
    ["Создаёт поды", "Хранит конфигурацию", "Масштабирует узлы", "Выдаёт IP подам"], topic="Ingress")

# =============================== CI/CD и Git ===============================
CI = "cicd"


@family("git.semver", CI, 2, "single", "Семантическое версионирование", time_limit=90)
def git_semver(rng: random.Random, _l):
    ma, mi, pa = rng.randint(1, 5), rng.randint(0, 9), rng.randint(0, 9)
    kind, desc = rng.choice([("patch", "исправлена ошибка без изменения API"),
                             ("minor", "добавлен новый обратно совместимый метод API"),
                             ("major", "удалён устаревший метод публичного API")])
    nxt = {"patch": f"{ma}.{mi}.{pa + 1}", "minor": f"{ma}.{mi + 1}.0", "major": f"{ma + 1}.0.0"}[kind]
    distract = [f"{ma}.{mi}.{pa + 1}", f"{ma}.{mi + 1}.0", f"{ma + 1}.0.0", f"{ma}.{mi + 1}.{pa}", f"{ma + 1}.{mi}.{pa}"]
    opts, key = options_from(rng, nxt, [d for d in distract if d != nxt])
    return Rendered(f"Текущая версия библиотеки `{ma}.{mi}.{pa}`. В релизе {desc}. Какой будет следующая версия по SemVer?",
                    "single", key, options=opts)


mcq("git.rebase", CI, 2, "Чем `git rebase main` отличается от `git merge main` в feature-ветке?",
    "rebase переписывает коммиты ветки поверх main (линейная история), merge создаёт коммит слияния",
    ["Ничем", "merge удаляет ветку", "rebase не меняет хеши коммитов", "rebase работает только с удалёнными ветками"],
    topic="Git")
mcq("git.reset", CI, 3, "Что делает `git reset --soft HEAD~1`?", "Отменяет последний коммит, оставляя изменения в индексе",
    ["Удаляет изменения последнего коммита из рабочей копии", "Создаёт обратный коммит", "Переключает ветку",
     "Удаляет ветку"], topic="Git")
mcq("git.revert_shared", CI, 3, "Как безопасно отменить коммит, уже отправленный в общую ветку?", "`git revert <hash>`",
    ["`git reset --hard` и `push --force`", "Удалить ветку", "`git commit --amend`", "`git stash`"], topic="Git")
mcq("git.bisect", CI, 4, "Для чего нужен `git bisect`?", "Бинарным поиском найти коммит, в котором появилась ошибка",
    ["Разделить репозиторий на два", "Слить две ветки", "Подписать коммиты", "Сжать историю"], topic="Git")
mcq("git.tracked_ignore", CI, 2, "Файл добавлен в .gitignore, но изменения в нём всё равно видны в `git status`. Почему?",
    "Файл уже отслеживается; нужно `git rm --cached`", ["Ошибка в Git", ".gitignore работает только для папок",
                                                        "Нужно перезапустить терминал", "Файл слишком большой"],
    topic="Git")
mcq("cd.canary", CI, 3, "Что такое канареечный релиз?", "Новая версия получает небольшую долю трафика, и при отсутствии "
    "проблем доля увеличивается", ["Две полные копии окружения с мгновенным переключением", "Релиз только по ночам",
                                   "Откат на прошлую версию", "Релиз без тестов"], topic="Стратегии деплоя")
mcq("cd.build_once", CI, 4, "Почему артефакт собирают один раз и продвигают по окружениям (dev → stage → prod)?",
    "Чтобы в prod попал ровно тот артефакт, что прошёл проверки", ["Чтобы экономить диск", "Так требует Docker",
                                                                    "Чтобы ускорить git clone", "Чтобы не писать тесты"],
    topic="Поставка")
mcq("cd.gitops", CI, 4, "В чём суть GitOps?", "Желаемое состояние инфраструктуры хранится в Git, агент приводит кластер "
    "к нему автоматически", ["Деплой вручную через kubectl", "Хранение бинарников в Git", "Код-ревью без CI",
                             "Мониторинг коммитов"], topic="GitOps")
mcq("cd.feature_flags", CI, 3, "Что дают feature flags?", "Отделяют деплой кода от включения функциональности для пользователей",
    ["Ускоряют сборку", "Заменяют тесты", "Шифруют конфигурацию", "Удаляют мёртвый код"], topic="Feature flags")
mcq("ci.pipeline_order", CI, 1, "Какой порядок шагов CI наиболее типичен?", "Сборка → тесты → анализ кода → публикация артефакта",
    ["Публикация → тесты → сборка", "Деплой в prod → тесты", "Тесты → сборка → код-ревью", "Публикация → сборка"],
    topic="CI")

# =============================== Мониторинг и SRE ===============================
O = "observability"


@family("sre.error_budget", O, 3, "numeric", "SLO и бюджет ошибок", time_limit=120)
def sre_error_budget(rng: random.Random, _l):
    slo = rng.choice([99.0, 99.5, 99.9, 99.95])
    days = rng.choice([7, 28, 30])
    minutes = days * 24 * 60 * (100 - slo) / 100
    return Rendered(f"SLO доступности — {slo}% за {days} дней. Сколько минут недоступности допускает бюджет ошибок? "
                    "Округлите до десятых.", "numeric", round(minutes, 1), tolerance=0.11)


@family("sre.percentile", O, 3, "numeric", "Перцентили задержек", time_limit=150)
def sre_percentile(rng: random.Random, _l):
    xs = [rng.randint(20, 120) for _ in range(17)] + [rng.randint(300, 900) for _ in range(3)]
    rng.shuffle(xs)
    p = rng.choice([50, 90, 95])
    s = sorted(xs)
    ans = s[math.ceil(p / 100 * len(s)) - 1]
    return Rendered(f"Задержки 20 запросов (мс): `{', '.join(map(str, xs))}`.\n\nНайдите p{p} методом ближайшего ранга "
                    f"(элемент с номером ⌈{p / 100}·N⌉ в отсортированном списке).", "numeric", ans)


@family("sre.burn_rate", O, 5, "numeric", "Скорость сгорания бюджета", time_limit=180)
def sre_burn_rate(rng: random.Random, _l):
    slo = rng.choice([99.9, 99.5])
    err = rng.choice([0.5, 1.0, 1.44, 2.0]) if slo == 99.9 else rng.choice([1.0, 2.5, 5.0])
    burn = err / (100 - slo)
    days = 30 / burn
    return Rendered(f"SLO {slo}% за 30 дней. Сейчас доля ошибочных запросов {err}%. За сколько дней будет израсходован "
                    "весь бюджет ошибок при такой скорости? Округлите до десятых.", "numeric", round(days, 1), tolerance=0.11)


multi("sre.golden", O, 2, "Какие сигналы относятся к «четырём золотым сигналам» мониторинга (Google SRE)?",
      ["Задержка (latency)", "Трафик", "Ошибки", "Насыщение (saturation)"], ["Число коммитов", "Покрытие тестами",
                                                                              "Размер образа"], topic="Мониторинг")
mcq("sre.counter_gauge", O, 2, "Каким типом метрики Prometheus описать текущее число активных соединений?", "Gauge",
    ["Counter", "Histogram только", "Summary только", "Info"], topic="Типы метрик")
mcq("sre.histogram", O, 4, "Почему для p99 по нескольким инстансам предпочитают histogram, а не summary?",
    "Бакеты гистограмм можно агрегировать между инстансами, квантили summary — нет", ["Summary не поддерживается",
                                                                                       "Histogram точнее всегда",
                                                                                       "Summary занимает больше места на диске",
                                                                                       "Histogram не требует хранения"],
    topic="Метрики")
mcq("sre.symptoms", O, 4, "Какой алерт лучше будить дежурного ночью?", "Рост доли ошибок у пользователей выше порога SLO",
    ["CPU на одном узле > 80%", "Заполнен диск на 60%", "Перезапуск одного пода", "Медленный cron-отчёт"],
    topic="Алертинг")
mcq("sre.tracing", O, 3, "Что даёт распределённая трассировка?", "Путь одного запроса через сервисы с временем каждого шага",
    ["Агрегаты CPU по кластеру", "Список коммитов", "Логи БД", "Состояние кэша"], topic="Трассировка")
mcq("sre.cardinality", O, 5, "Почему нельзя добавлять user_id как label метрики Prometheus?",
    "Взрыв кардинальности: число временных рядов растёт с числом пользователей", ["Prometheus не поддерживает строки",
                                                                                 "Это нарушает 152-ФЗ всегда",
                                                                                 "label должен быть числом",
                                                                                 "Метрики станут counter"],
    topic="Метрики")
mcq("sre.mttr", O, 2, "Что измеряет MTTR?", "Среднее время восстановления после инцидента",
    ["Среднее время между релизами", "Время ответа API", "Время сборки", "Число инцидентов"], topic="Метрики надёжности")
mcq("sre.log_levels", O, 1, "Какой уровень логирования подходит для ошибки, из-за которой запрос пользователя не выполнен?",
    "ERROR", ["DEBUG", "TRACE", "INFO", "Логировать не нужно"], topic="Логирование")
mcq("sre.postmortem", O, 3, "Какой принцип лежит в основе постмортема в SRE-культуре?", "Безобвинительность: ищем "
    "системные причины и действия по улучшению", ["Найти виновного", "Не документировать инциденты",
                                                 "Откатить все изменения за месяц", "Скрыть инцидент от пользователей"],
    topic="Инциденты")
