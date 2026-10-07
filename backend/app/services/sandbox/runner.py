"""Песочница: исполнение кода кандидата (Python, JavaScript) в изолированном процессе.

Слои изоляции в Docker-стенде (контейнер sandbox, см. sandbox/Dockerfile и docker-compose.yml):
  1) контейнер без сети (network_mode: none — ни интернета, ни других контейнеров; бэкенд обращается к песочнице через
     Unix-сокет на общем томе), файловая система только для чтения, кроме /tmp в памяти (без права просмотра каталога),
     все Linux-capabilities сброшены, no-new-privileges, init-процесс подбирает завершённые процессы, лимиты числа
     процессов, памяти и CPU;
  2) каждый запуск — новый процесс в отдельном временном каталоге со случайным именем, от непривилегированного
     пользователя, с лимитами ядра (CPU-время, память, размер файлов, число открытых файлов и процессов) и общим
     таймаутом; после запуска завершается вся группа процессов, а «сбежавшие» из неё (setsid) — зачисткой;
  3) ожидаемые ответы в песочницу не передаются: она возвращает только значения функции, сравнение с ожидаемым —
     на бэкенде. Поэтому код кандидата не может «подсмотреть» ответы скрытых тестов.
Без Docker (локальная разработка и автотесты) тот же модуль работает обычным подпроцессом с таймаутом.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

MAX_CODE = 20_000
MAX_INPUTS = 60
# Только в контейнере песочницы (у неё свой пользователь): лимит числа процессов и зачистка «сбежавших» процессов.
# На машине разработчика эти меры не применяются — счётчик процессов общий для пользователя.
IN_CONTAINER = os.environ.get("SANDBOX_CONTAINER") == "1"
NPROC = 64
ENTRY_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,63}$")

PY_HARNESS = r'''
import contextlib, io, json, sys, time

def _safe(v, depth=0):
    if depth > 50:
        return repr(v)
    if v is None or isinstance(v, (bool, int, float, str)):
        if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
            return repr(v)
        return v
    if isinstance(v, (list, tuple)):
        return [_safe(x, depth + 1) for x in v]
    if isinstance(v, (set, frozenset)):
        items = [_safe(x, depth + 1) for x in v]
        try:
            return sorted(items)
        except TypeError:
            return sorted(items, key=repr)
    if isinstance(v, dict):
        return {str(k): _safe(x, depth + 1) for k, x in v.items()}
    return repr(v)

def main():
    spec = json.load(open("input.json", encoding="utf-8"))
    out = {"status": "ok", "results": []}
    ns = {"__name__": "__solution__"}
    try:
        src = open("solution.py", encoding="utf-8").read()
        exec(compile(src, "solution.py", "exec"), ns)
    except SyntaxError as e:
        out = {"status": "compile_error", "error": "SyntaxError: %s (строка %s)" % (e.msg, e.lineno), "results": []}
    except BaseException as e:
        out = {"status": "compile_error", "error": "%s: %s" % (type(e).__name__, e), "results": []}
    fn = ns.get(spec["entrypoint"]) if out["status"] == "ok" else None
    if out["status"] == "ok" and not callable(fn):
        out = {"status": "compile_error", "error": "Не найдена функция %s" % spec["entrypoint"], "results": []}
    if out["status"] == "ok":
        sys.setrecursionlimit(3000)
        for args in spec["inputs"]:
            buf = io.StringIO()
            t0 = time.perf_counter()
            try:
                with contextlib.redirect_stdout(buf):
                    val = fn(*args)
                res = {"ok": True, "value": _safe(val)}
            except RecursionError:
                res = {"ok": False, "error": "RecursionError: слишком глубокая рекурсия"}
            except BaseException as e:
                res = {"ok": False, "error": ("%s: %s" % (type(e).__name__, e))[:500]}
            res["stdout"] = buf.getvalue()[:2000]
            res["ms"] = round((time.perf_counter() - t0) * 1000, 2)
            out["results"].append(res)
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

main()
'''

JS_HARNESS = r'''
'use strict';
const fs = require('fs');
const path = require('path');
const Module = require('module');
const { performance } = require('perf_hooks');

function safe(v, depth = 0) {
  if (depth > 50) return String(v);
  if (v === undefined || v === null) return null;
  if (typeof v === 'number') return Number.isFinite(v) ? v : String(v);
  if (typeof v === 'bigint') return String(v);
  if (typeof v === 'boolean' || typeof v === 'string') return v;
  if (Array.isArray(v)) return v.map(x => safe(x, depth + 1));
  if (v instanceof Set) return [...v].map(x => safe(x, depth + 1));
  if (v instanceof Map) return Object.fromEntries([...v].map(([k, x]) => [String(k), safe(x, depth + 1)]));
  if (typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, safe(x, depth + 1)]));
  return String(v);
}

async function main() {
  const spec = JSON.parse(fs.readFileSync('input.json', 'utf8'));
  const E = spec.entrypoint;
  let out = { status: 'ok', results: [] };
  let fn;
  try {
    const src = fs.readFileSync('solution.js', 'utf8');
    const file = path.resolve('solution.js');
    const m = new Module(file);
    m.filename = file;
    m.paths = [];
    m._compile(src + `\n;module.exports.__entry = (typeof ${E} !== 'undefined') ? ${E} : (module.exports && module.exports.${E});`, file);
    fn = m.exports.__entry;
    if (typeof fn !== 'function') out = { status: 'compile_error', error: `Не найдена функция ${E}`, results: [] };
  } catch (e) {
    out = { status: 'compile_error', error: String(e && e.stack ? e.stack.split('\n').slice(0, 2).join(' ') : e), results: [] };
  }
  if (out.status === 'ok') {
    for (const args of spec.inputs) {
      const lines = [];
      const orig = { log: console.log, error: console.error };
      console.log = (...a) => lines.push(a.map(String).join(' '));
      console.error = console.log;
      const t0 = performance.now();
      let res;
      try {
        let val = fn(...args);
        if (val && typeof val.then === 'function') val = await val;
        res = { ok: true, value: safe(val) };
      } catch (e) {
        res = { ok: false, error: String(e && e.name ? `${e.name}: ${e.message}` : e).slice(0, 500) };
      }
      console.log = orig.log; console.error = orig.error;
      res.stdout = lines.join('\n').slice(0, 2000);
      res.ms = Math.round((performance.now() - t0) * 100) / 100;
      out.results.push(res);
    }
  }
  fs.writeFileSync('output.json', JSON.stringify(out));
}
main();
'''

LANGS = {
    "python": {"file": "solution.py", "harness": ("harness.py", PY_HARNESS)},
    "javascript": {"file": "solution.js", "harness": ("harness.js", JS_HARNESS)},
}


def _command(language: str, memory_mb: int) -> list[str]:
    if language == "python":
        return [sys.executable, "-I", "-S", "-B", "harness.py"]
    node = shutil.which("node") or "node"
    return [node, f"--max-old-space-size={max(32, memory_mb // 2)}", "--stack-size=4096", "harness.js"]


def _preexec(language: str, cpu_s: int, memory_mb: int):
    """Лимиты ядра для процесса решения (только POSIX)."""
    def apply() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        if language == "python":  # V8 резервирует много виртуальной памяти — для Node лимит задаётся флагом
            resource.setrlimit(resource.RLIMIT_AS, (memory_mb << 20, memory_mb << 20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if IN_CONTAINER:  # fork-бомба упирается в лимит раньше, чем в лимит процессов контейнера
            resource.setrlimit(resource.RLIMIT_NPROC, (NPROC, NPROC))
    return apply


def run(language: str, code: str, entrypoint: str, inputs: list, time_limit_ms: int = 2000,
        memory_mb: int = 256) -> dict:
    """Запускает функцию `entrypoint` из `code` на каждом наборе аргументов `inputs`.
    Возвращает статус (ok | compile_error | timeout | error), значения по каждому набору, stdout и время."""
    if language not in LANGS:
        return {"status": "error", "error": f"Язык не поддерживается: {language}", "results": []}
    if not ENTRY_RE.match(entrypoint or ""):
        return {"status": "error", "error": "Некорректное имя функции", "results": []}
    if len(code) > MAX_CODE or len(inputs) > MAX_INPUTS:
        return {"status": "error", "error": "Слишком большой код или слишком много тестов", "results": []}
    spec = LANGS[language]
    tmp = tempfile.mkdtemp(prefix="run-")
    t0 = time.monotonic()
    proc = None
    try:
        with open(os.path.join(tmp, spec["file"]), "w", encoding="utf-8") as f:
            f.write(code)
        name, harness = spec["harness"]
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
            f.write(harness)
        with open(os.path.join(tmp, "input.json"), "w", encoding="utf-8") as f:
            json.dump({"entrypoint": entrypoint, "inputs": inputs}, f, ensure_ascii=False)
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": tmp, "LANG": "C.UTF-8",
               "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        if os.name == "nt":  # без SYSTEMROOT Python на Windows не стартует
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        cpu_s = max(1, -(-time_limit_ms // 1000))
        kwargs: dict = {"cwd": tmp, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                        "env": env}
        if os.name == "posix":
            kwargs |= {"start_new_session": True, "preexec_fn": _preexec(language, cpu_s, memory_mb)}
        else:
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(_command(language, memory_mb), **kwargs)
        wall = time_limit_ms / 1000 + 1.5  # запас на старт интерпретатора
        try:
            _, err = proc.communicate(timeout=wall)
        except subprocess.TimeoutExpired:
            _kill(proc)
            proc.communicate()
            return {"status": "timeout", "error": f"Превышено время выполнения ({time_limit_ms} мс на все тесты)",
                    "results": [], "duration_ms": round((time.monotonic() - t0) * 1000)}
        duration = round((time.monotonic() - t0) * 1000)
        out_file = os.path.join(tmp, "output.json")
        if not os.path.exists(out_file):
            stderr = err.decode("utf-8", "replace")[-1500:]
            reason = "превышен лимит памяти или процесс завершён системой" if proc.returncode and proc.returncode < 0 \
                else "процесс завершился без результата"
            return {"status": "error", "error": f"Ошибка выполнения: {reason}", "stderr": stderr, "results": [],
                    "duration_ms": duration}
        with open(out_file, encoding="utf-8") as f:
            data = json.load(f)
        data["duration_ms"] = duration
        data["stderr"] = err.decode("utf-8", "replace")[-1500:]
        if not isinstance(data.get("results"), list) or (data.get("status") == "ok" and len(data["results"]) != len(inputs)):
            return {"status": "error", "error": "Некорректный результат выполнения", "results": [], "duration_ms": duration}
        return data
    except (OSError, ValueError) as exc:
        return {"status": "error", "error": f"Песочница: {exc}", "results": []}
    finally:
        if proc is not None:
            _kill(proc)  # процессы, оставшиеся в группе запуска после выхода решения
        _reap_orphans()
        shutil.rmtree(tmp, ignore_errors=True)


def _kill(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _reap_orphans() -> None:
    """Процессы, сбежавшие из группы запуска (setsid, двойной fork), в контейнере переходят к init (PID 1) —
    их завершаем. Сервис (его не трогаем явно) и проверки здоровья (их родитель вне контейнера) не затрагиваются."""
    if not IN_CONTAINER:
        return
    me = os.getpid()
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) in (1, me):
            continue
        try:
            with open(f"/proc/{name}/stat", "rb") as f:
                ppid = int(f.read().rsplit(b")", 1)[1].split()[1])
            if ppid == 1:
                os.kill(int(name), signal.SIGKILL)
        except (OSError, ValueError, IndexError):
            pass


def available_languages() -> list[str]:
    langs = ["python"]
    if shutil.which("node"):
        langs.append("javascript")
    return langs
