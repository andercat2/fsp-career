"""Домены данных: статистика, машинное обучение, глубокое обучение, pandas/NumPy, продуктовая аналитика."""
from __future__ import annotations

import math
import random
import statistics as st
from collections import Counter

import numpy as np

from app.services.testing.bank.core import Rendered, family, mcq, multi, options_from

# =============================== Статистика ===============================
S = "statistics"


@family("stat.mean_median", S, 1, "numeric", "Среднее и медиана", time_limit=90)
def stat_mean_median(rng: random.Random, _l):
    xs = [rng.randint(1, 30) for _ in range(rng.choice([7, 8, 9]))]
    if rng.random() < 0.5:
        return Rendered(f"Найдите медиану выборки: `{xs}`.", "numeric", st.median(xs), tolerance=0.01)
    return Rendered(f"Найдите среднее выборки: `{xs}`. Округлите до десятых.", "numeric", round(st.mean(xs), 1), tolerance=0.051)


@family("stat.variance", S, 2, "numeric", "Дисперсия", time_limit=150)
def stat_variance(rng: random.Random, _l):
    m = rng.randint(5, 15)
    devs = rng.choice([[-2, -1, 0, 1, 2], [-3, -1, 0, 1, 3], [-4, -2, 0, 2, 4], [-2, -2, 0, 2, 2]])
    xs = [m + d for d in devs]
    rng.shuffle(xs)
    return Rendered(f"Найдите несмещённую выборочную дисперсию (делитель n − 1) для выборки `{xs}`.", "numeric",
                    round(st.variance(xs), 2), tolerance=0.01)


@family("stat.bayes", S, 4, "numeric", "Формула Байеса", time_limit=240)
def stat_bayes(rng: random.Random, _l):
    prev = rng.choice([0.5, 1, 2, 5])
    sens = rng.choice([90, 95, 99])
    spec = rng.choice([90, 95, 98, 99])
    p, se, sp = prev / 100, sens / 100, spec / 100
    post = p * se / (p * se + (1 - p) * (1 - sp))
    return Rendered(f"Доля мошеннических транзакций — {prev}%. Антифрод-модель помечает {sens}% мошеннических и ошибочно "
                    f"помечает {100 - spec}% честных транзакций. Какова вероятность (в %), что помеченная транзакция "
                    "действительно мошенническая? Округлите до десятых.", "numeric", round(post * 100, 1), tolerance=0.11)


@family("stat.binomial", S, 3, "numeric", "Биномиальное распределение", time_limit=150)
def stat_binomial(rng: random.Random, _l):
    n = rng.randint(4, 6)
    k = rng.randint(1, n - 1)
    pr = math.comb(n, k) / 2**n * 100
    return Rendered(f"Честную монету подбрасывают {n} раз. Какова вероятность (в %), что орёл выпадет ровно {k} раз(а)? "
                    "Округлите до десятых.", "numeric", round(pr, 1), tolerance=0.11)


@family("stat.expected", S, 2, "numeric", "Математическое ожидание", time_limit=120)
def stat_expected(rng: random.Random, _l):
    win, lose = rng.choice([30, 40, 50, 60]), rng.choice([5, 8, 10, 12])
    ev = win / 6 - lose * 5 / 6
    return Rendered(f"Игра: бросаем кубик. Выпала 6 — выигрыш {win} ₽, иначе — проигрыш {lose} ₽. Каков ожидаемый выигрыш "
                    "за одну игру, ₽? Округлите до сотых.", "numeric", round(ev, 2), tolerance=0.011)


@family("stat.se", S, 3, "numeric", "Стандартная ошибка среднего", time_limit=120)
def stat_se(rng: random.Random, _l):
    sigma = rng.choice([10, 12, 15, 20, 30])
    n = rng.choice([16, 25, 36, 64, 100])
    return Rendered(f"Стандартное отклонение метрики — {sigma}, размер выборки — {n}. Чему равна стандартная ошибка среднего? "
                    "Округлите до сотых.", "numeric", round(sigma / math.sqrt(n), 2), tolerance=0.011)


@family("stat.zscore", S, 2, "numeric", "z-оценка", time_limit=90)
def stat_zscore(rng: random.Random, _l):
    mu, sd = rng.choice([100, 50, 70]), rng.choice([10, 15, 20])
    x = mu + sd * rng.choice([-2, -1.5, -1, 0.5, 1, 1.5, 2, 2.5])
    return Rendered(f"Время загрузки страницы ~ N(μ = {mu}, σ = {sd}) мс. Чему равна z-оценка значения {x:g} мс?", "numeric",
                    round((x - mu) / sd, 2), tolerance=0.011)


@family("stat.bonferroni", S, 4, "numeric", "Множественные сравнения", time_limit=120)
def stat_bonferroni(rng: random.Random, _l):
    alpha, m = rng.choice([0.05, 0.1]), rng.choice([4, 5, 10, 20])
    return Rendered(f"В эксперименте проверяют {m} гипотез с общим уровнем значимости α = {alpha}. Какой порог p-value "
                    "использовать для каждой гипотезы по поправке Бонферрони?", "numeric", alpha / m, tolerance=1e-4)


mcq("stat.pvalue", S, 3, "Что такое p-value?", "Вероятность получить такой же или более экстремальный результат, "
    "если нулевая гипотеза верна", ["Вероятность того, что нулевая гипотеза верна", "Вероятность ошибки II рода",
                                    "Размер эффекта", "Вероятность того, что альтернативная гипотеза верна"],
    topic="Проверка гипотез")
mcq("stat.type1", S, 2, "Что такое ошибка I рода?", "Отвергнуть верную нулевую гипотезу (ложноположительный вывод)",
    ["Не отвергнуть ложную нулевую гипотезу", "Ошибка в данных", "Неправильно выбранный тест",
     "Слишком маленькая выборка"], topic="Проверка гипотез")
mcq("stat.clt", S, 3, "Что утверждает центральная предельная теорема?", "Распределение выборочного среднего при большом n "
    "приближается к нормальному независимо от исходного распределения (при конечной дисперсии)",
    ["Любые данные распределены нормально", "Выборочное среднее всегда равно истинному",
     "Дисперсия растёт с n", "Медиана равна среднему"], topic="ЦПТ")
mcq("stat.ci", S, 4, "Как корректно интерпретировать 95%-й доверительный интервал?",
    "Если повторять эксперимент много раз, около 95% построенных интервалов накроют истинное значение",
    ["Истинное значение с вероятностью 95% лежит в этом конкретном интервале — строго по частотному подходу",
     "95% данных лежат в интервале", "p-value равно 0.95", "Ошибка измерения не превышает 5%"], topic="Доверительные интервалы")
mcq("stat.causation", S, 1, "Продажи мороженого коррелируют с числом утоплений. Какой вывод корректен?",
    "Возможна общая причина (жара); корреляция не доказывает причинность", ["Мороженое вызывает утопления",
                                                                            "Утопления повышают продажи",
                                                                            "Связь случайна всегда",
                                                                            "Нужно запретить мороженое"],
    topic="Корреляция и причинность")
mcq("stat.simpson", S, 5, "Новая версия лучше старой в каждом сегменте (мобильные и десктоп), но хуже в сумме. Как "
    "называется эффект?", "Парадокс Симпсона", ["Эффект новизны", "Регрессия к среднему", "Ошибка выжившего",
                                                "Эффект подглядывания"], topic="Парадоксы")
mcq("stat.power", S, 4, "Что такое мощность статистического теста?", "Вероятность обнаружить эффект, если он есть (1 − β)",
    ["Вероятность ошибки I рода", "Размер выборки", "Величина p-value", "Доля выбросов"], topic="Мощность")

# =============================== Машинное обучение ===============================
M = "ml"


@family("ml.metrics", M, 2, "numeric", "Метрики классификации", time_limit=150)
def ml_metrics(rng: random.Random, _l):
    tp, fp, fn, tn = rng.randint(20, 90), rng.randint(5, 40), rng.randint(5, 40), rng.randint(100, 400)
    metric = rng.choice(["precision", "recall", "F1", "accuracy"])
    pr, rc = tp / (tp + fp), tp / (tp + fn)
    val = {"precision": pr, "recall": rc, "F1": 2 * pr * rc / (pr + rc), "accuracy": (tp + tn) / (tp + fp + fn + tn)}[metric]
    return Rendered(f"Матрица ошибок бинарного классификатора: TP = {tp}, FP = {fp}, FN = {fn}, TN = {tn}. "
                    f"Чему равен **{metric}**? Округлите до трёх знаков.", "numeric", round(val, 3), tolerance=0.0015)


@family("ml.gini", M, 4, "numeric", "Критерии разбиения деревьев", time_limit=180)
def ml_gini(rng: random.Random, _l):
    counts = [rng.randint(2, 12) for _ in range(rng.choice([2, 3]))]
    n = sum(counts)
    if rng.random() < 0.5:
        val = 1 - sum((c / n) ** 2 for c in counts)
        what = "индекс Джини"
    else:
        val = -sum((c / n) * math.log2(c / n) for c in counts)
        what = "энтропию (log₂)"
    return Rendered(f"В узле дерева решений объекты распределены по классам: {counts}. Вычислите {what} узла. "
                    "Округлите до трёх знаков.", "numeric", round(val, 3), tolerance=0.0015)


@family("ml.regression_loss", M, 1, "numeric", "Функции потерь регрессии", time_limit=120)
def ml_regression_loss(rng: random.Random, _l):
    y = [rng.randint(1, 10) for _ in range(4)]
    p = [v + rng.choice([-3, -2, -1, 0, 1, 2, 3]) for v in y]
    metric = rng.choice(["MAE", "MSE"])
    val = (sum(abs(a - b) for a, b in zip(y, p, strict=True)) if metric == "MAE"
           else sum((a - b) ** 2 for a, b in zip(y, p, strict=True))) / 4
    return Rendered(f"Истинные значения `{y}`, предсказания `{p}`. Вычислите {metric}.", "numeric", val, tolerance=0.01)


@family("ml.knn", M, 3, "input", "k ближайших соседей", time_limit=150)
def ml_knn(rng: random.Random, _l):
    while True:
        pts = sorted(rng.sample(range(0, 30), 8))
        labels = [rng.choice("AB") for _ in pts]
        q = rng.randint(3, 27)
        if q in pts:
            continue
        dists = sorted(((abs(x - q), x, lab) for x, lab in zip(pts, labels, strict=True)))
        if dists[2][0] == dists[3][0]:
            continue  # без равенств на границе k
        k = rng.choice([1, 3])
        if k == 1 and dists[0][0] == dists[1][0]:
            continue
        vote = Counter(lab for _, _, lab in dists[:k]).most_common(1)[0][0]
        break
    pts_s = ", ".join(f"{x}→{lab}" for x, lab in zip(pts, labels, strict=True))
    return Rendered(f"Одномерные обучающие точки (значение→класс): `{pts_s}`. Какой класс предскажет kNN с k = {k} "
                    f"(евклидово расстояние, голосование большинством) для x = {q}?", "input", vote, norm="lower")


@family("ml.kfold", M, 2, "numeric", "Кросс-валидация", time_limit=90)
def ml_kfold(rng: random.Random, _l):
    k = rng.choice([4, 5, 10])
    n = k * rng.randint(50, 300)
    return Rendered(f"Датасет из {n} объектов, {k}-fold кросс-валидация. Сколько объектов в обучающей выборке на каждой итерации?",
                    "numeric", n - n // k)


mcq("ml.overfit", M, 1, "Ошибка на обучении падает, а на валидации растёт. Что происходит?", "Переобучение",
    ["Недообучение", "Утечка данных", "Нормальная сходимость", "Слишком маленький learning rate"], topic="Переобучение")
mcq("ml.l1", M, 3, "Чем L1-регуляризация отличается от L2 по влиянию на веса?", "L1 зануляет часть весов (разреженность), "
    "L2 равномерно уменьшает веса", ["L2 зануляет веса", "Ничем", "L1 увеличивает веса", "L1 применяется только к нейросетям"],
    topic="Регуляризация")
mcq("ml.bias_variance", M, 3, "Что обычно происходит при увеличении глубины дерева решений?",
    "Смещение уменьшается, разброс (variance) растёт", ["Смещение растёт, разброс падает", "Оба растут",
                                                       "Оба падают", "Ничего не меняется"], topic="Bias-variance")
mcq("ml.leak_scaling", M, 4, "Почему StandardScaler нельзя обучать на всём датасете до разбиения на train/test?",
    "Статистики теста просочатся в обучение — оценка качества будет завышена", ["Это замедлит обучение",
                                                                                 "Scaler не работает с тестом",
                                                                                 "Признаки станут категориальными",
                                                                                 "Так делать правильно"],
    topic="Утечка данных")
mcq("ml.imbalance", M, 3, "Положительный класс — 1% данных. Какая метрика информативнее accuracy?",
    "PR-AUC (или F1 по положительному классу)", ["Accuracy всё равно лучшая", "MSE", "R²", "Число деревьев"],
    topic="Несбалансированные классы")
mcq("ml.knn_scaling", M, 2, "Почему перед kNN признаки масштабируют?", "Иначе признаки с большим диапазоном доминируют в расстоянии",
    ["kNN не работает с float", "Чтобы уменьшить число соседей", "Чтобы удалить выбросы", "Масштабирование не нужно"],
    topic="Предобработка")
mcq("ml.rf_boosting", M, 3, "Чем случайный лес отличается от градиентного бустинга?", "Лес строит деревья независимо и "
    "усредняет, бустинг — последовательно, исправляя ошибки предыдущих", ["Ничем", "Бустинг использует одно дерево",
                                                                         "Лес обучается последовательно",
                                                                         "Лес работает только для регрессии"],
    topic="Ансамбли")
mcq("ml.roc_auc", M, 3, "Как интерпретировать ROC-AUC = 0.8?", "Вероятность того, что случайный положительный объект "
    "получит больший скор, чем случайный отрицательный, — 0.8", ["Точность 80%", "80% объектов классифицированы верно",
                                                                  "Recall = 0.8", "Ошибка 20%"], topic="ROC-AUC")
mcq("ml.target_leak", M, 4, "Модель предсказывает отток клиента. Какой признак, вероятнее всего, является утечкой таргета?",
    "Дата закрытия договора", ["Число обращений в поддержку за прошлый месяц", "Тариф", "Регион",
                               "Длительность обслуживания"], topic="Утечка данных")
mcq("ml.kmeans", M, 2, "Что минимизирует алгоритм k-means?", "Сумму квадратов расстояний объектов до центров своих кластеров",
    ["Число кластеров", "Расстояние между центрами", "Энтропию классов", "Log-loss"], topic="Кластеризация")
mcq("ml.permutation", M, 4, "Как работает permutation importance?", "Перемешивает значения признака и измеряет падение "
    "качества модели", ["Считает число разбиений по признаку", "Удаляет признак и переобучает модель всегда",
                        "Берёт модуль веса признака", "Считает корреляцию с таргетом"], topic="Интерпретация")
mcq("ml.calibration", M, 5, "Модель хорошо ранжирует, но её «вероятность 0.9» сбывается в 60% случаев. Что поможет?",
    "Калибровка вероятностей (Platt scaling, изотоническая регрессия)", ["Увеличить число деревьев",
                                                                         "Сменить метрику на accuracy",
                                                                         "Удалить признаки", "Снизить learning rate"],
    topic="Калибровка")

# =============================== Глубокое обучение ===============================
DL = "deep_learning"


@family("dl.conv_out", DL, 3, "numeric", "Размер выхода свёртки", time_limit=120)
def dl_conv_out(rng: random.Random, _l):
    while True:
        w, k, p, s = rng.choice([28, 32, 64, 224, 56]), rng.choice([3, 5, 7]), rng.choice([0, 1, 2, 3]), rng.choice([1, 2])
        if (w - k + 2 * p) % s == 0:
            break
    return Rendered(f"Вход {w}×{w}, свёртка ядром {k}×{k}, padding = {p}, stride = {s}. Каков размер выхода по одной стороне?",
                    "numeric", (w - k + 2 * p) // s + 1)


@family("dl.params", DL, 2, "numeric", "Число параметров слоёв", time_limit=150)
def dl_params(rng: random.Random, _l):
    if rng.random() < 0.5:
        i, h, o = rng.choice([64, 128, 256, 784]), rng.choice([32, 64, 128]), rng.choice([2, 10])
        return Rendered(f"Полносвязная сеть: вход {i} → скрытый слой {h} → выход {o}, у всех слоёв есть смещения. "
                        "Сколько обучаемых параметров?", "numeric", i * h + h + h * o + o)
    k, cin, cout = rng.choice([3, 5]), rng.choice([3, 16, 32]), rng.choice([16, 32, 64])
    return Rendered(f"Свёрточный слой Conv2d: {cin} входных каналов, {cout} фильтров, ядро {k}×{k}, со смещением. "
                    "Сколько обучаемых параметров?", "numeric", k * k * cin * cout + cout)


mcq("dl.vanishing", DL, 3, "Какой приём помогает бороться с затуханием градиентов в глубоких сетях?",
    "Остаточные связи (residual connections) и ReLU-подобные активации", ["Сигмоида во всех слоях", "Уменьшение батча до 1",
                                                                         "Удаление нормализации", "Увеличение глубины"],
    topic="Обучение глубоких сетей")
mcq("dl.dropout", DL, 2, "Что делает dropout во время обучения?", "Случайно обнуляет часть активаций, снижая переобучение",
    ["Удаляет слои", "Уменьшает learning rate", "Нормализует входы", "Удаляет объекты из батча"], topic="Регуляризация")
mcq("dl.batchnorm", DL, 3, "Чем BatchNorm ведёт себя по-разному при обучении и инференсе?",
    "При обучении использует статистики батча, при инференсе — накопленные скользящие средние",
    ["Ничем", "При инференсе отключается полностью", "При обучении использует только веса", "При инференсе пересчитывает батч"],
    topic="Нормализация")
mcq("dl.attention", DL, 4, "Какова вычислительная сложность self-attention по длине последовательности n?", "O(n²)",
    ["O(n)", "O(log n)", "O(n³)", "O(1)"], topic="Трансформеры")
mcq("dl.transfer", DL, 2, "Что такое transfer learning?", "Дообучение модели, предобученной на большой задаче, под свою",
    ["Перенос модели на другой сервер", "Обучение без данных", "Конвертация в ONNX", "Сжатие модели"],
    topic="Transfer learning")
mcq("dl.ce", DL, 2, "Какую функцию потерь обычно используют для многоклассовой классификации?", "Кросс-энтропию",
    ["MSE", "Hinge для регрессии", "MAE", "Huber"], topic="Функции потерь")
mcq("dl.lora", DL, 5, "В чём идея LoRA при дообучении больших моделей?", "Заморозить веса и обучать низкоранговые добавки "
    "к матрицам весов", ["Обучать все веса с малым lr", "Удалить половину слоёв", "Квантовать модель в 1 бит",
                         "Обучать только эмбеддинги"], topic="Дообучение LLM")
mcq("dl.positional", DL, 4, "Зачем трансформеру позиционное кодирование?", "Self-attention инвариантен к перестановкам "
    "токенов и сам по себе не знает их порядка", ["Чтобы ускорить обучение", "Чтобы уменьшить словарь",
                                                 "Для нормализации", "Для маскирования паддингов"], topic="Трансформеры")

# =============================== pandas и NumPy ===============================
DT = "data_tools"


def _shape(t: tuple) -> str:
    return "(" + ", ".join(map(str, t)) + ("," if len(t) == 1 else "") + ")"


@family("np.broadcast", DT, 3, "input", "Broadcasting в NumPy", time_limit=120)
def np_broadcast(rng: random.Random, _l):
    a, b, c = rng.sample([2, 3, 4, 5, 6], 3)
    variant = rng.randrange(4)
    if variant == 0:
        s1, s2, res = (a, 1), (b,), f"{a} {b}"
    elif variant == 1:
        s1, s2, res = (a, b), (b,), f"{a} {b}"
    elif variant == 2:
        s1, s2, res = (a, 1, c), (b, 1), f"{a} {b} {c}"
    else:
        s1, s2, res = (a, b), (a,), "ошибка"
    return Rendered(f"Какая форма у результата `np.ones({_shape(s1)}) + np.ones({_shape(s2)})`? Введите размеры через "
                    "пробел или слово «ошибка», если операция невозможна.", "input", res,
                    accepted=["error", "valueerror"] if res == "ошибка" else [])


_SLICES = {"1:": slice(1, None), ":2": slice(None, 2), "::2": slice(None, None, 2), "1:3": slice(1, 3),
           "-2:": slice(-2, None)}


@family("np.slicing", DT, 2, "numeric", "Срезы массивов", time_limit=120)
def np_slicing(rng: random.Random, _l):
    r, c = rng.choice([3, 4]), rng.choice([4, 5])
    arr = np.arange(r * c).reshape(r, c)
    rs, cs = rng.choice(list(_SLICES)), rng.choice(["::2", "1:3", "-2:"])
    val = int(arr[_SLICES[rs], _SLICES[cs]].sum())
    return Rendered("Что выведет код?", "numeric", val,
                    code=f"import numpy as np\narr = np.arange({r * c}).reshape({r}, {c})\nprint(arr[{rs}, {cs}].sum())",
                    code_lang="python")


@family("pd.groupby", DT, 3, "numeric", "Группировка в pandas", time_limit=150)
def pd_groupby(rng: random.Random, _l):
    cities = rng.sample(["Москва", "Казань", "Томск", "Сочи"], 3)
    rows = [(rng.choice(cities), rng.randint(1, 20) * 10) for _ in range(8)]
    city = rng.choice(sorted({c for c, _ in rows}))
    agg = rng.choice(["sum", "mean", "count", "max"])
    vals = [v for c, v in rows if c == city]
    ans = {"sum": sum(vals), "mean": round(st.mean(vals), 2), "count": len(vals), "max": max(vals)}[agg]
    table = "| city | sales |\n|---|---|\n" + "\n".join(f"| {c} | {v} |" for c, v in rows)
    return Rendered(f"DataFrame `df`:\n\n{table}\n\nЧто вернёт `df.groupby('city')['sales'].{agg}()['{city}']`? "
                    "Дробный ответ округлите до сотых.", "numeric", ans, tolerance=0.011)


@family("pd.merge", DT, 4, "numeric", "Соединение таблиц в pandas", time_limit=180)
def pd_merge(rng: random.Random, _l):
    left = [rng.choice("abcd") for _ in range(5)]
    right = [rng.choice("abce") for _ in range(4)]
    how = rng.choice(["inner", "left", "outer"])
    lc, rc = Counter(left), Counter(right)
    inner = sum(lc[k] * rc[k] for k in lc)
    lonly = sum(v for k, v in lc.items() if k not in rc)
    ronly = sum(v for k, v in rc.items() if k not in lc)
    ans = {"inner": inner, "left": inner + lonly, "outer": inner + lonly + ronly}[how]
    return Rendered(f"`a` — DataFrame с колонкой `k` = `{left}`, `b` — с колонкой `k` = `{right}`. "
                    f"Сколько строк вернёт `pd.merge(a, b, on='k', how='{how}')`?", "numeric", ans,
                    explanation="Дублирующиеся ключи дают декартово произведение совпадающих строк.")


@family("pd.nan_mean", DT, 2, "numeric", "Пропуски в данных", time_limit=120)
def pd_nan_mean(rng: random.Random, _l):
    vals = [rng.randint(1, 10) * 2 for _ in range(5)]
    idx = rng.sample(range(5), 2)
    shown = ["np.nan" if i in idx else str(v) for i, v in enumerate(vals)]
    rest = [v for i, v in enumerate(vals) if i not in idx]
    return Rendered("Что выведет код? Округлите до сотых.", "numeric", round(st.mean(rest), 2), tolerance=0.011,
                    code=f"s = pd.Series([{', '.join(shown)}])\nprint(s.mean())", code_lang="python")


mcq("pd.loc_iloc", DT, 2, "Чем `df.loc` отличается от `df.iloc`?", "loc индексирует по меткам, iloc — по целочисленным позициям",
    ["Ничем", "iloc работает только со строками", "loc быстрее всегда", "iloc индексирует по меткам"], topic="Индексация")
mcq("pd.copy_warning", DT, 4, "Почему возникает SettingWithCopyWarning?", "Присваивание идёт в объект, который может быть "
    "копией среза, и исходный DataFrame может не измениться", ["Из-за дубликатов индекса", "Из-за NaN в столбце",
                                                              "Из-за слишком большого DataFrame", "Из-за типа category"],
    topic="pandas")
mcq("pd.vectorize", DT, 3, "Как быстрее всего посчитать новый столбец `df['c'] = df['a'] * df['b']` для миллиона строк?",
    "Векторной операцией над столбцами", ["Через `iterrows()`", "Через `apply(axis=1)`", "Через цикл по индексу",
                                          "Через `itertuples()` и append"], topic="Производительность")
mcq("pd.category", DT, 4, "Когда тип `category` заметно экономит память?", "Когда в строковом столбце мало уникальных значений",
    ["Когда все значения уникальны", "Для числовых столбцов всегда", "Для дат", "Никогда"], topic="Типы данных")

# =============================== Продуктовая аналитика ===============================
AN = "analytics"


@family("an.conversion", AN, 1, "numeric", "Конверсия", time_limit=90)
def an_conversion(rng: random.Random, _l):
    v = rng.randint(20, 90) * 100
    p = rng.randint(50, int(v * 0.12))
    return Rendered(f"Сайт посетили {v} пользователей, покупку совершили {p}. Какова конверсия, %? Округлите до сотых.",
                    "numeric", round(p / v * 100, 2), tolerance=0.011)


@family("an.funnel", AN, 2, "numeric", "Воронка", time_limit=120)
def an_funnel(rng: random.Random, _l):
    steps = [rng.choice([40, 50, 60, 70, 80]) for _ in range(3)]
    total = steps[0] / 100 * steps[1] / 100 * steps[2] / 100 * 100
    return Rendered(f"Воронка: каталог → карточка товара {steps[0]}%, карточка → корзина {steps[1]}%, корзина → оплата "
                    f"{steps[2]}%. Какая сквозная конверсия из каталога в оплату, %? Округлите до сотых.", "numeric",
                    round(total, 2), tolerance=0.011)


@family("an.arpu", AN, 2, "numeric", "ARPU и ARPPU", time_limit=120)
def an_arpu(rng: random.Random, _l):
    users = rng.randint(10, 50) * 1000
    payers = rng.randint(3, 12) * users // 100
    rev = payers * rng.randint(300, 1500)
    metric = rng.choice(["ARPU", "ARPPU"])
    val = rev / users if metric == "ARPU" else rev / payers
    return Rendered(f"За месяц: {users} активных пользователей, {payers} платящих, выручка {rev} ₽. Чему равен {metric}, ₽? "
                    "Округлите до сотых.", "numeric", round(val, 2), tolerance=0.011)


@family("an.retention", AN, 2, "numeric", "Retention и stickiness", time_limit=120)
def an_retention(rng: random.Random, _l):
    if rng.random() < 0.5:
        n = rng.randint(10, 40) * 100
        m = rng.randint(n // 10, n // 3)
        return Rendered(f"В когорте {n} новых пользователей, на 7-й день вернулись {m}. Retention 7-го дня, %? "
                        "Округлите до сотых.", "numeric", round(m / n * 100, 2), tolerance=0.011)
    mau = rng.randint(50, 200) * 1000
    dau = rng.randint(mau // 10, mau // 3)
    return Rendered(f"DAU = {dau}, MAU = {mau}. Чему равен stickiness (DAU/MAU), %? Округлите до сотых.", "numeric",
                    round(dau / mau * 100, 2), tolerance=0.011)


@family("an.ltv", AN, 3, "numeric", "LTV", time_limit=150)
def an_ltv(rng: random.Random, _l):
    arpu = rng.choice([200, 300, 450, 600])
    churn = rng.choice([5, 10, 20, 25])
    margin = rng.choice([40, 50, 60])
    return Rendered(f"Ежемесячный ARPU — {arpu} ₽, ежемесячный отток — {churn}% (постоянный), маржинальность — {margin}%. "
                    "Оцените LTV клиента по марже, ₽ (средний срок жизни = 1 / отток).", "numeric",
                    round(arpu * margin / 100 / (churn / 100), 2), tolerance=0.5)


@family("an.pp_vs_pct", AN, 1, "single", "Процентные пункты", time_limit=90)
def an_pp_vs_pct(rng: random.Random, _l):
    a = rng.choice([2, 4, 5, 8, 10])
    b = a + rng.choice([1, 2, 3])
    rel = round((b - a) / a * 100, 1)
    correct = f"на {b - a} п.п., или на {rel:g}% относительно"
    opts, key = options_from(rng, correct, [f"на {b - a}% относительно и на {rel:g} п.п.", f"на {rel:g} п.п.",
                                            f"на {b - a}% и это одно и то же", f"на {round(b / a * 100):g}%"])
    return Rendered(f"Конверсия выросла с {a}% до {b}%. Как корректно описать изменение?", "single", key, options=opts)


@family("an.ab_z", AN, 5, "numeric", "A/B-тест для конверсий", time_limit=240)
def an_ab_z(rng: random.Random, _l):
    n = rng.choice([2000, 4000, 5000])
    ca = rng.randint(int(n * 0.08), int(n * 0.11))
    cb = ca + rng.randint(int(n * 0.005), int(n * 0.025))
    pa, pb = ca / n, cb / n
    pool = (ca + cb) / (2 * n)
    z = (pb - pa) / math.sqrt(pool * (1 - pool) * 2 / n)
    return Rendered(f"A/B-тест: в группе A {n} пользователей и {ca} конверсий, в группе B {n} пользователей и {cb} "
                    "конверсий. Вычислите z-статистику двухвыборочного z-теста для долей с объединённой оценкой p. "
                    "Округлите до сотых.", "numeric", round(z, 2), tolerance=0.02)


@family("an.sample_size", AN, 4, "single", "Размер выборки и MDE", time_limit=120)
def an_sample_size(rng: random.Random, _l):
    f = rng.choice([2, 3, 4])
    opts, key = options_from(rng, f"Примерно в {f * f} раз(а)", [f"Примерно в {f} раз(а)", f"Примерно в {f * 2} раз(а)",
                                                                  "Не изменится", f"Примерно в {f ** 3} раз(а)"])
    return Rendered(f"Хотим уменьшить минимальный детектируемый эффект (MDE) в {f} раза при тех же α и мощности. "
                    "Как изменится необходимый размер выборки?", "single", key, options=opts,
                    explanation="Размер выборки обратно пропорционален квадрату MDE.")


mcq("an.peeking", AN, 4, "Аналитик ежедневно смотрит p-value и останавливает тест при первом p < 0.05. Чем это плохо?",
    "Многократные проверки сильно завышают вероятность ложноположительного результата", ["Тест станет слишком долгим",
                                                                                       "Снизится мощность до нуля",
                                                                                       "Это стандартная практика",
                                                                                       "Невозможно посчитать p-value"],
    topic="Проблема подглядывания")
mcq("an.srm", AN, 5, "Ожидали сплит 50/50, получили 50 600 / 49 400 пользователей при 100 000. Что проверить в первую очередь?",
    "Sample Ratio Mismatch — ошибку в рандомизации или логировании", ["Эффект новизны", "Сезонность",
                                                                      "Выбросы в выручке", "Ничего, это нормально"],
    topic="Валидность эксперимента")
mcq("an.cuped", AN, 5, "Что делает CUPED?", "Снижает дисперсию метрики, используя данные о пользователях до эксперимента",
    ["Увеличивает размер выборки", "Исправляет SRM", "Убирает эффект новизны", "Заменяет t-тест на тест Манна — Уитни"],
    topic="Снижение дисперсии")
mcq("an.median_revenue", AN, 2, "Почему средний чек может вводить в заблуждение при наличии крупных покупателей?",
    "Среднее чувствительно к выбросам; медиана устойчивее", ["Среднее всегда меньше медианы", "Среднее нельзя посчитать",
                                                             "Медиана чувствительнее к выбросам", "Это не так"],
    topic="Описательные статистики")
mcq("an.guardrail", AN, 3, "Что такое guardrail-метрика в A/B-тесте?", "Метрика, которая не должна ухудшиться (например, "
    "отмены, жалобы, скорость)", ["Главная целевая метрика", "Метрика только для мобильных", "Метрика размера выборки",
                                  "Метрика числа тестов"], topic="Дизайн эксперимента")
mcq("an.novelty", AN, 4, "Новая кнопка дала +15% кликов в первые дни, затем эффект исчез. Как называется явление?",
    "Эффект новизны", ["Парадокс Симпсона", "SRM", "Регрессия к среднему", "Каннибализация"], topic="Интерпретация")
mcq("an.cohort", AN, 3, "Зачем строить когортный анализ retention, а не смотреть общий DAU?",
    "Чтобы отделить поведение пользователей разных периодов привлечения от роста базы", ["Чтобы увеличить DAU",
                                                                                         "Чтобы посчитать выручку",
                                                                                         "Это одно и то же",
                                                                                         "Чтобы сократить данные"],
    topic="Когорты")
multi("an.dirty_data", AN, 2, "Какие проверки качества данных стоит сделать перед расчётом метрики?",
      ["Дубликаты событий", "Пропуски и NULL", "Тестовые и служебные аккаунты", "Смена часовых поясов"],
      ["Цвет дашборда", "Число колонок в таблице"], topic="Качество данных")
