"""Демо-задачи с кодом корректны: каждая проходит валидацию формы работодателя, её эталон проходит все свои тесты
в песочнице, а синтетические решения дают картину для демонстрации — верное, частичное и копия под антиплагиат."""
import pytest

from app.schemas import CodeTaskSpec, TaskIn
from app.seed.code_tasks_data import CODE_TASKS, PHONES_COPY, PHONES_GOOD, PHONES_PARTIAL
from app.services.sandbox.antiplagiarism import THRESHOLD, similarity
from app.services.sandbox.runner import available_languages
from app.services.sandbox.tasks import evaluate


def _spec(task: dict) -> CodeTaskSpec:
    return CodeTaskSpec(**{k: task[k] for k in CodeTaskSpec.model_fields if k in task})


@pytest.mark.parametrize("task", CODE_TASKS, ids=lambda t: t["entrypoint"])
def test_demo_task_reference_passes_all_tests(task):
    TaskIn(**{k: v for k, v in task.items() if k != "company"})  # задачу можно открыть и сохранить в форме
    if task["code_language"] not in available_languages():
        pytest.skip(f"{task['code_language']} недоступен в этом окружении")
    res = evaluate(_spec(task), task["reference_solution"])
    assert res["status"] == "ok" and res["passed"] == res["total"], res


def test_plagiarism_threshold_separates_copies_from_independent_solutions():
    """Корпус validation/plagiarism_validation.py: все замаскированные копии выше порога, независимые решения — ниже."""
    from validation.plagiarism_validation import _pairs

    copies, independent = _pairs()
    assert len(copies) >= 6 and len(independent) >= 19
    assert min(copies) >= THRESHOLD > max(independent)


def test_demo_submissions_for_phone_task():
    task = next(t for t in CODE_TASKS if t["entrypoint"] == "normalize_phones")
    spec = _spec(task)
    assert evaluate(spec, PHONES_GOOD)["passed"] == len(task["tests"])
    assert evaluate(spec, PHONES_COPY)["passed"] == len(task["tests"])
    assert 0 < evaluate(spec, PHONES_PARTIAL)["passed"] < len(task["tests"])
    assert similarity(PHONES_COPY, PHONES_GOOD, "python", task["starter_code"]) >= THRESHOLD
    assert similarity(PHONES_PARTIAL, PHONES_GOOD, "python", task["starter_code"]) < THRESHOLD
    assert similarity(PHONES_GOOD, task["reference_solution"], "python", task["starter_code"]) < THRESHOLD
