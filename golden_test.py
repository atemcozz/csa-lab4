import contextlib
import io
import logging
import os
import tempfile

import machine_runner
import pytest
import translator

LOG_MAX_FIRST_LINES = 1000
LOG_MAX_LAST_LINES = 1000


def truncate_log(log, first_lines, last_lines):
    log_lines = str(log).splitlines()
    if len(log_lines) <= first_lines + last_lines:
        return log

    res_lines = []

    res_lines.extend(log_lines[:first_lines])
    res_lines.append(f"Truncated {len(log_lines) - first_lines - last_lines} lines...")
    res_lines.extend(log_lines[-last_lines:])
    return "\n".join(res_lines)

@pytest.mark.golden_test("golden/*.yml")
def test_translator_and_machine(golden, caplog):
    caplog.set_level(logging.DEBUG)
    caplog.handler.setFormatter(logging.Formatter("%(message)s"))

    # Создаём временную папку для тестирования приложения.
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Готовим имена файлов для входных и выходных данных.
        source = os.path.join(tmpdirname, "source.c")
        input_stream = os.path.join(tmpdirname, "input.yml")
        target = os.path.join(tmpdirname, "target.bin")
        target_hex = os.path.join(tmpdirname, "target.bin.hex")

        # Записываем входные данные в файлы. Данные берутся из теста.
        with open(source, "w", encoding="utf-8") as file:
            file.write(golden["in_source"])
        with open(input_stream, "w", encoding="utf-8") as file:
            file.write(golden["in_stdin"])

        # Запускаем транслятор и собираем весь стандартный вывод в переменную
        # stdout
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            translator.translate(source, target, target_hex, verbose=False)
            print("============================================================")
            memory_size = golden.get("memory_size", 8192)
            tick_limit = golden.get("limit", 10000)
            machine_runner.run_simulation(
                target, input_stream, memory_size, tick_limit, verbose=True)

        # Выходные данные также считываем в переменные.
        with open(target, "rb") as file:
            code = file.read()
        with open(target_hex, encoding="utf-8") as file:
            code_hex = file.read()


        trunc_caplog = truncate_log(caplog.text, LOG_MAX_FIRST_LINES, LOG_MAX_LAST_LINES)

        # Проверяем, что ожидания соответствуют реальности.
        assert code == golden.out["out_code"]
        assert code_hex == golden.out["out_code_hex"]
        assert stdout.getvalue() == golden.out["out_stdout"]
        assert trunc_caplog + "\nEOF" == golden.out.get("out_log")
