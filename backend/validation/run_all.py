"""Полный прогон процедуры валидации и сводка в Markdown (validation/reports/SUMMARY.md).

Запуск: python -m validation.run_all   (≈5 минут на обычном ноутбуке)
"""
from __future__ import annotations

import time

from validation import cat_validation, matching_validation, nlp_validation, plagiarism_validation
from validation.common import REPORTS


RESUME_FIELDS = {
    "name": "ФИО", "email": "E-mail", "phone": "Телефон", "telegram": "Telegram", "github": "GitHub", "city": "Город",
    "relocation": "Готовность к переезду", "headline": "Желаемая должность", "salary": "Желаемая зарплата",
    "formats": "Формат работы", "years_within_0_5": "Стаж (±0,5 года)", "experience_count": "Число мест работы",
    "company": "Компания", "position": "Должность", "start_date": "Дата начала работы", "university": "Учебное заведение",
    "edu_year": "Год окончания", "languages": "Языки", "about": "О себе",
}


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


UNCONFIRMED_NAMES = {"hidden": "Скрывать (как было)", "shown_1.0": "**Показывать со статусом — продукт**",
                     "shown_0.85": "Показывать, множитель 0.85", "shown_0.7": "Показывать, множитель 0.7",
                     "shown_0.55": "Показывать, множитель 0.55", "shown_0.4": "Показывать, множитель 0.4",
                     "tier": "Строго после всех подтверждённых"}


def unconfirmed_lines(match: dict) -> list[str]:
    u = match.get("unconfirmed")
    if not u:
        return []
    bt = u["unconfirmed_by_true_level"]
    out = ["### Неподтверждённые грейды: скрывать или показывать ниже", "",
           f"Сценарий: {pct(u['stop_share'])} кандидатов после неподтверждения заявленного грейда не пересдают уровень "
           f"ниже сразу. Без категории — {u['unconfirmed_candidates']} из {u['population']}: истинный уровень как заявлен у "
           f"{bt.get('true_level_as_claimed', 0)} (тест ошибся), ниже заявленного — у {bt.get('true_level_lower', 0)}.", "",
           "| Вариант | P@10 | nDCG@10 | Нерелевантных в топ-10 | «Завысивших» в топ-10 | Неподтверждённых в топ-10 | "
           "Релевантные неподтверждённые в топ-20 |", "|---|---|---|---|---|---|---|"]
    for k, title in UNCONFIRMED_NAMES.items():
        v = u["summary"][k]
        out.append(f"| {title} | {v['p10']} ± {v['p10_ci95']} | {v['ndcg10']} | {pct(v['irrelevant_in_top10'])} | "
                   f"{pct(v['inflated_in_top10'])} | {pct(v['unconfirmed_in_top10'])} | {pct(v['relevant_unconfirmed_in_top20'])} |")
    return out + [""]


def express_lines(cat: dict) -> list[str]:
    e = cat.get("express")
    if not e:
        return []
    f, x = e["full"], e["express"]
    out = ["### Экспресс-тест против полного", "",
           f"Одна популяция ({e['config']['population']} кандидатов); грейд в обоих режимах — самый вероятный по ответам. "
           "Длительность — по модели времени ответа симуляции (в среднем 55% лимита задания).", "",
           f"| Метрика | Полный тест | Экспресс ({e['config']['items']} заданий, лимит ≤ {e['config']['max_time_limit_sec'] // 60} мин) |",
           "|---|---|---|",
           f"| Заданий | {f['items']} | {x['items']} |",
           f"| Длительность, мин: среднее / p90 | {f['est_duration_min']} / {f['est_duration_p90_min']} | {x['est_duration_min']} / {x['est_duration_p90_min']} |",
           f"| Корреляция θ̂ с истинным θ / RMSE | {f['pearson_r']} / {f['rmse']} | {x['pearson_r']} / {x['rmse']} |",
           f"| Грейд совпал с истинным | {pct(f['grade_exact'])} | {pct(x['grade_exact'])} |",
           f"| Грейд в пределах ±1 ступени | {pct(f['grade_within_one'])} | {pct(x['grade_within_one'])} |",
           f"| Разделение соседних грейдов (AUC, среднее) | {f['auc_adjacent_mean']} | {x['auc_adjacent_mean']} |",
           f"| Калибровка вероятности грейда (ECE) | {f['calibration']['ece']} | {x['calibration']['ece']} |", "",
           "Перебор длины экспресс-теста и лимита времени задания:", "",
           "| Заданий | Лимит задания | Длительность, мин | r(θ̂, θ) | Грейд совпал | ±1 ступень | AUC соседних грейдов |",
           "|---|---|---|---|---|---|---|"]
    for r in e["sweep"]:
        out.append(f"| {r['items']}{' (выбрано)' if r['chosen'] else ''} | {r['max_time_limit_sec']} с | {r['est_duration_min']} | "
                   f"{r['pearson_r']} | {pct(r['grade_exact'])} | {pct(r['grade_within_one'])} | {r['auc_adjacent_mean']} |")
    return out + ["", "Экспресс-тест категорию не присваивает: это пробная оценка уровня с вероятностями грейдов.", ""]


def summary_md(cat: dict, match: dict, nlp: dict, plag: dict) -> str:
    rec, gr, la, dd, ms = cat["recovery"], cat["grades"], cat["leak_attack"], cat["drift_detection"], cat["misspecification"]
    s = match["summary"]
    sp = match["summary_with_proficiency"]
    lines = [
        "# Результаты валидации", "",
        f"Сгенерировано: {time.strftime('%Y-%m-%d %H:%M')}. Все эксперименты воспроизводимы: `python -m validation.run_all`.", "",
        "## 1. Механика тестирования (адаптивный тест, IRT)", "",
        f"Популяция: {cat['config']['population']} синтетических кандидатов, 35% завышают заявленный грейд.", "",
        "| Метрика | Значение |", "|---|---|",
        f"| Корреляция оценки уровня θ̂ с истинным θ | {rec['pearson_r']} |",
        f"| RMSE оценки уровня | {rec['rmse']} |",
        f"| Средняя длина теста (заданий) | {rec['test_length']['mean']} (p10–p90: {rec['test_length']['p10']}–{rec['test_length']['p90']}) |",
        f"| Точность решения «грейд подтверждён» | {pct(rec['decision']['accuracy'])} |",
        f"| Ложные подтверждения / ложные отказы | {pct(rec['decision']['false_confirm_rate'])} / {pct(rec['decision']['false_reject_rate'])} |",
        f"| Итоговый грейд совпал с истинным | {pct(gr['grade_exact_accuracy'])} (самооценка: {pct(gr['self_declared_exact_accuracy'])}) |",
        f"| Грейд в пределах ±1 ступени | {pct(gr['grade_within_one'])} |",
        f"| Завышение грейда | {pct(gr['overgrading_rate_test'])} (самооценка: {pct(gr['overgrading_rate_self_declared'])}) |",
        f"| Повторное прохождение: тот же грейд | {pct(gr['retest']['grade_agreement'])}, взвешенная κ = {gr['retest']['weighted_kappa']}, r(θ̂₁, θ̂₂) = {gr['retest']['theta_test_retest_r']} |",
        f"| Грейд ниже по тому же тесту (P ≥ {rec['lower_grade_from_same_test']['threshold']}): предлагается / точность | "
        f"{pct(rec['lower_grade_from_same_test']['offered_share'])} неподтверждений / {pct(rec['lower_grade_from_same_test']['precision'])} |",
        f"| Если бы «уверенный» результат сразу повышал грейд: точность | {pct(rec['higher_grade_from_same_test']['precision'])} "
        f"({rec['higher_grade_from_same_test']['confirmed_strong']} сессий) — поэтому повышение только отдельным тестом |",
        f"| Дискриминативность заданий: медиана D / доля D ≥ 0.3 | {cat['discrimination']['median_D']} / {pct(cat['discrimination']['share_D_ge_0_3'])} |",
        f"| Использовано семейств банка / макс. экспозиция | {pct(cat['exposure']['used_share'])} / {pct(cat['exposure']['max_exposure_rate'])} |",
        f"| Совпадение идентичных вопросов у двух кандидатов одного уровня | {pct(cat['overlap']['mean_identical_question_overlap'])} |",
        "", "### Атака «слитой базой» (заявляют грейд на ступень выше)", "",
        "| Система | Честно (K=0) | K=5 | K=25 | K=100 |", "|---|---|---|---|---|",
    ]
    for name, title in (("fixed_form", "Фиксированный тест (20 статичных заданий)"),
                        ("static_bank", "Адаптивный тест без параметрических вариантов"),
                        ("ours", "Наша система: завышение"), ):
        r = la["inflation_rate"][name]
        lines.append(f"| {title} | {pct(r['0'])} | {pct(r['5'])} | {pct(r['25'])} | {pct(r['100'])} |")
    u = la["undetected_inflation_rate"]["ours"]
    d = la["detection_rate"]["ours"]
    lines += [
        f"| Наша система: незамеченное завышение | {pct(u['0'])} | {pct(u['5'])} | {pct(u['25'])} | {pct(u['100'])} |",
        f"| Наша система: доля помеченных сессий | {pct(la['honest_flag_rate']['ours'])} | {pct(d['5'])} | {pct(d['25'])} | {pct(d['100'])} |",
        "", f"Обнаружение утечки статичных заданий по дрейфу решаемости ({dd['specialization']}, порог z>3): " + ", ".join(
            f"после {k} прохождений — TPR {pct(v['3.0']['tpr'])}, FPR {pct(v['3.0']['fpr'])}" for k, v in dd["checkpoints"].items()) + ".",
        "", f"Ошибки априорной калибровки (b ± 0.4, a × e^N(0,0.25)): точность грейда {pct(ms['grade_accuracy']['prior_params'])} "
            f"на априорных параметрах против {pct(ms['grade_accuracy']['oracle_true_params'])} у «оракула»; онлайн-калибровка "
            f"снижает ошибку трудности с {ms['b_rmse_prior']} до {ms['b_rmse_after_calibration']}.", "",
        *express_lines(cat),
        "## 2. Механика подбора", "",
        f"{match['setup']['candidates']} кандидатов, {match['setup']['needs']} потребностей; релевантность — из латентной истины.", "",
        "| Система | P@10 | nDCG@10 | MRR | Нерелевантных в топ-10 | «Завысивших» в топ-10 |", "|---|---|---|---|---|---|",
    ]
    names = {"keyword": "Поиск по ключевым словам (TF-IDF по резюме)", "filters": "Фильтры по самоописанию",
             "ours": "**Наша система**", "ours_nlp": "Наша система, потребность из текста (NLP)",
             "ours_self_declared_category": "Абляция: категория из самоописания", "ours_no_fsp": "Абляция: без ФСП",
             "ours_no_verification": "Абляция: без проверки навыков тестом"}
    for k, title in names.items():
        v = s[k]
        lines.append(f"| {title} | {v['p10']} ± {v['p10_ci95']} | {v['ndcg10']} | {v['mrr']} | {pct(v['irrelevant_in_top10'])} | {pct(v['inflated_in_top10'])} |")
    lines += ["", "С учётом уровня владения навыками (P@10 / nDCG@10): " + "; ".join(
        f"{names[k].strip('*')}: {sp[k]['p10']} / {sp[k]['ndcg10']}" for k in ("keyword", "filters", "ours")) + ".",
              "", f"Время ранжирования пула до {match['setup']['candidates']} кандидатов: {match['latency_ms']['mean']} мс в среднем.", "",
              *unconfirmed_lines(match),
              "## 3. NLP", "",
              f"Вакансии ({nlp['vacancies']['n']} размеченных текстов): специализация {pct(nlp['vacancies']['specialization_accuracy']['hybrid'])} "
              f"(только модель — {pct(nlp['vacancies']['specialization_accuracy']['model_only'])}), грейды {pct(nlp['vacancies']['grades_exact'])}, "
              f"навыки F1 {nlp['vacancies']['skills']['f1']}, вилка {pct(nlp['vacancies']['salary_exact'])}, формат {pct(nlp['vacancies']['work_format'])}.", "",
              f"Резюме ({nlp['resumes']['n']} синтетических PDF: половина — двухколоночная вёрстка экспорта hh.ru, половина — "
              f"свободный текст; эталон → PDF → pdfminer.six → парсер). Навыки F1 {nlp['resumes']['skills_f1']} "
              f"(hh.ru {nlp['resumes']['skills_f1_by_template']['hh']}, свободный {nlp['resumes']['skills_f1_by_template']['free']}), "
              f"средняя ошибка стажа {nlp['resumes']['experience_mae_years']} г.", "",
              "| Поле | hh.ru | Свободный текст | Всего |", "|---|---|---|---|",
              *[f"| {RESUME_FIELDS.get(k, k)} | {pct(nlp['resumes']['field_accuracy_by_template']['hh'].get(k))} | "
                f"{pct(nlp['resumes']['field_accuracy_by_template']['free'].get(k))} | {pct(v)} |"
                for k, v in nlp['resumes']['field_accuracy'].items()], "",
              "## 4. Антиплагиат задач с кодом", "",
              f"Корпус: {len(plag['tasks'])} демо-задачи, {plag['copies']['n']} замаскированных копий (переименование, "
              f"комментарии, форматирование, неиспользуемый код) и {plag['independent_pairs']['n']} пар независимых решений "
              f"одной задачи; каждое решение проверено в песочнице на тестах задачи.", "",
              f"Порог {plag['threshold']}: найдено копий {plag['copies']['detected']} из {plag['copies']['n']} (минимальное "
              f"сходство {plag['copies']['min']}), ложных срабатываний {plag['independent_pairs']['false_positives']} из "
              f"{plag['independent_pairs']['n']} (максимальное сходство независимых решений {plag['independent_pairs']['max']}).", "",
              "| k-грамма | Окно | Найдено копий | Мин. сходство копий | Ложных срабатываний | Макс. сходство независимых |",
              "|---|---|---|---|---|---|",
              *[f"| {r['k']}{' (выбрано)' if r['chosen'] else ''} | {r['window']} | {r['copies_detected']} из {plag['copies']['n']} | "
                f"{r['copies_min']} | {r['independent_false_positives']} из {plag['independent_pairs']['n']} | {r['independent_max']} |"
                for r in plag['parameters']['sweep']], "",
              "## Ограничения", "",
              "- Эталон синтетический: проверяются свойства процедур при известной истине. Для продуктива нужен пилот с "
              "экспертной оценкой ФСП (план — в документации) и онлайн-калибровка заданий на реальных ответах.",
              "- Тексты вакансий для проверки NLP написаны командой; перед запуском — проверка на выборке реальных вакансий.",
              "- Корпус антиплагиата мал, и параметры выбраны на нём перебором (таблица выше); на реальных решениях порог "
              "нужно перепроверить.", ""]
    return "\n".join(lines)


def main() -> None:
    t0 = time.time()
    cat = cat_validation.main()
    match = matching_validation.main()
    nlp = nlp_validation.main()
    plag = plagiarism_validation.main()
    (REPORTS / "SUMMARY.md").write_text(summary_md(cat, match, nlp, plag), encoding="utf-8", newline="\n")
    print(f"Готово за {time.time() - t0:.0f} с. Сводка: {REPORTS / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
