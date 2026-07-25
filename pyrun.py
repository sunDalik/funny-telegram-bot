import ast
import asyncio
import html
import json
import logging
import re
from collections.abc import Collection
from dataclasses import dataclass

import eryx
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CallbackContext, CommandHandler

import db
from db import U
from _secrets import banned_user_ids
from utils import CommandTrigger, get_username_by_id

logger = logging.getLogger(__name__)

EXEC_TIMEOUT_MS = 10_000
HOST_TIMEOUT_S = 15
MAX_MEMORY_BYTES = 128 * 1024 * 1024
MAX_PENDING_RUNS = 5

MAX_OUTPUT_CHARS = 8000
MAX_VAR_KEY_LEN = 64
MAX_VAR_KEYS = 1000
SQLITE_INT_MIN = -(2 ** 63)
SQLITE_INT_MAX = 2 ** 63 - 1

HELP_TEXT = (
    "Присылай питон на прогонку: <code>/py 300+13</code>\n\n"
    "Хочешь сохранить свой шедевр? Кидай <code>/set</code> на сообщение с <code>/py</code> или сразу <code>/set lol /py code</code>.\n"
    "Хочешь подглядеть чужой код? <code>/rawget lol</code>\n\n"
    "Сделал ошибку? Отредактируй сообщение, и я его перезапущу.\n"
    "Сломал все что можно? Запусти <code>/pyundo</code>, и я забуду о твоем позоре.\n\n"
    "Хочется чего-то большего от жизни? Попробуй:\n"
    "<code>quote() -> str</code>: сообщение, в ответ на которое запустили скрипт\n"
    "<code>quote_user() -> str</code>: тот, кто это сообщение написал\n"
    "<code>user() -> str</code>: тот, кто запустил скрипт\n"
    "<code>users() -> dict[str, int]</code>: словарь друзей и их айди\n"
    "<code>numset(k: str, v: int) -> int</code>: запомнить число между запусками\n"
    "<code>numget(k: str) -> int</code>: вспомнить число (или 0)\n"
    "<code>numall() -> dict[str, int]</code>: словарь всех чисел"
)

# Injected in /py code
_PROLOG = '''\
import json as _pyrun_json
_pyrun_kv = _pyrun_json.loads({kv})
_pyrun_ctx = _pyrun_json.loads({ctx})
_pyrun_kv_w = {{}}
def numget(k): return _pyrun_kv.get(k, 0)
def numset(k, v):
    if not isinstance(k, str) or not str: raise TypeError("numset: key must be a non-empty str")
    if not isinstance(v, int): raise TypeError("numset: value must be an int")
    _pyrun_kv[k] = _pyrun_kv_w[k] = int(v) # wrap bool in int
    return int(v)
def numall(): return _pyrun_kv
def quote(): return _pyrun_ctx["quote"]
def quote_user(): return _pyrun_ctx["quote_user"]
def user(): return _pyrun_ctx["user"]
def users(): return _pyrun_ctx["users"]
_pyrun_last = None
'''
_EPILOG = '''
import json as _pyrun_json2
try:
    _pyrun_json2.dumps(_pyrun_last)
    _pyrun_res = {"last_value": _pyrun_last, "w": _pyrun_kv_w}
except (TypeError, ValueError):
    _pyrun_res = {"last_repr": repr(_pyrun_last), "w": _pyrun_kv_w}
'''

RESULT_VAR = "_pyrun_res"
PROLOG_LINES = _PROLOG.count("\n")


def _get_sandbox_src(src: str, trigger: CommandTrigger, vars: dict[str, int], user: str, users: dict[str, int]) -> str:
    def assign_last_expr_to_var(src: str) -> str:
        try:
            flags = ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
            tree = compile(src, "<user>", "exec", flags=flags, dont_inherit=True)
        except (SyntaxError, ValueError):
            return src
        if not tree.body or not isinstance(last_expr := tree.body[-1], ast.Expr):
            return src
        if last_expr.end_lineno is None or last_expr.end_col_offset is None:
            return src

        bsrc = src.encode()
        line_starts = [0, *(idx + 1 for idx, byte in enumerate(bsrc) if byte == 0x0A)]
        start = line_starts[last_expr.lineno - 1] + last_expr.col_offset
        end = line_starts[last_expr.end_lineno - 1] + last_expr.end_col_offset
        bres = bsrc[:start] + b"_pyrun_last = (" + bsrc[start:end] + b")" + bsrc[end:]
        return bres.decode()

    context_json = json.dumps({
        "quote": trigger.quote_text,
        "quote_user": trigger.quote_user,
        "user": user,
        "users": users,
    })
    prolog = _PROLOG.format(kv=json.dumps(json.dumps(vars)), ctx=json.dumps(context_json))
    return prolog + assign_last_expr_to_var(src) + "\n" + _EPILOG


def _clear_sandbox_frames(traceback: str) -> str:
    def replace_frame(frame: re.Match[str]) -> str:
        if frame["filename"] != "<user>":
            return ""
        line = int(frame["line"])
        location = "" if line <= PROLOG_LINES else f"line {line - PROLOG_LINES}, "
        if function := frame["function"]:
            location += f"in {function}"
        else:
            location = location.removesuffix(", ")
        context = "" if line <= PROLOG_LINES else frame["context"]
        return f'{frame["prefix"]}{frame["indent"]}{location}{context}'

    return re.sub(
        r'(?P<prefix>\A|\n)(?P<indent>[^\S\n]*)File "(?P<filename>[^"]*)", '
        r'line (?P<line>\d+)(?:, in (?P<function>[^\n]*))?'
        r'(?P<context>(?:\n(?P=indent) .*)*)',
        replace_frame,
        traceback.rstrip(),
    ).strip()


def _check_var_writes(writes: object, old_keys: Collection[str]) -> tuple[dict[str, int], str]:
    if not isinstance(writes, dict):
        return {}, "Твои numset'ы потеряны :("
    validated: dict[str, int] = {}
    for key, value in writes.items():
        if not isinstance(key, str) or not key:
            return {}, "Может назовешь свой numset ключ нормальной строкой?"
        if len(key) > MAX_VAR_KEY_LEN:
            return {}, f"Ключ на {len(key)} символов в numset, ты серьезно?"
        if not isinstance(value, int):
            return {}, f"Как ты думаешь, что значит num в numset? Подскажу: твой numset \"{key}\" должен быть числом."
        if not SQLITE_INT_MIN <= value <= SQLITE_INT_MAX:
            return {}, f"Твой numset \"{key}\" выходит за границы int64. Ничего не жмет?"
        validated[key] = value
    if len(validated.keys() | old_keys) > MAX_VAR_KEYS:
        return {}, f"Куда тебе столько numset'ов? Давай ограничимся {MAX_VAR_KEYS}."
    return validated, ""


@dataclass
class RunResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    value: str = ""
    error: str = ""
    write_error: str = ""


class _Capture:
    def __init__(self):
        self.chunks: list[str] = []
        self.length = 0

    def __call__(self, chunk: str) -> None:
        if chunk := chunk[:MAX_OUTPUT_CHARS - self.length]:
            self.chunks.append(chunk)
            self.length += len(chunk)

    def text(self) -> str:
        return "".join(self.chunks)


_execution_lock = asyncio.Lock()
_pending_runs = 0


async def run_code(code: str, trigger: CommandTrigger) -> RunResult | None:
    global _pending_runs
    if trigger.user_id in banned_user_ids:
        logger.info(f"[py] Ignored banned user {trigger.user_id}")
        return None
    if _pending_runs >= MAX_PENDING_RUNS:
        return RunResult(ok=False, error="Смерти моей захотел? Подожди, пока предыдущие /py отработают, прежде чем новыми закидывать.")

    _pending_runs += 1
    try:
        async with _execution_lock:
            return await _run_locked(code, trigger)
    finally:
        _pending_runs -= 1


async def _run_locked(code: str, trigger: CommandTrigger) -> RunResult:
    stored_values = db.get().load_py_vars()
    username = get_username_by_id(trigger.user_id) if trigger.user_id else ""
    users = db.get().fetch_many(db.User, f"SELECT * FROM {U.TABLE}")
    full_code = _get_sandbox_src(code, trigger, stored_values, username, {u.username: u.user_id for u in users})
    stdout, stderr = _Capture(), _Capture()

    def run_sandbox():
        limits = eryx.ResourceLimits(execution_timeout_ms=EXEC_TIMEOUT_MS, max_memory_bytes=MAX_MEMORY_BYTES)
        sandbox = eryx.Sandbox(resource_limits=limits, result_variable=RESULT_VAR, on_stdout=stdout, on_stderr=stderr)
        return sandbox.execute(full_code)

    def fail(error: str, stderr_text: str) -> RunResult:
        return RunResult(ok=False, stdout=stdout.text(), stderr=stderr_text, error=error)

    try:
        sandbox_result = await asyncio.wait_for(asyncio.to_thread(run_sandbox), HOST_TIMEOUT_S)
    except eryx.TimeoutError:
        return fail(f"Твой код завис. В следующий раз уложись в {EXEC_TIMEOUT_MS // 1000} секунд.", stderr.text())
    except (eryx.ResourceLimitError, eryx.ExecutionError) as error:
        error_text, stderr_text = str(error), stderr.text()
        if isinstance(error, eryx.ExecutionError):
            trace_start = error_text.find("Traceback (most recent call last):\n")
            user_stderr = error_text[:trace_start] if trace_start >= 0 else ""
            trace = _clear_sandbox_frames(error_text[trace_start:] if trace_start >= 0 else error_text)
            if error_text and stderr_text.endswith(error_text):
                stderr_text = stderr_text[:-len(error_text)] + user_stderr
            if re.search(r"(?:\A|\n)MemoryError\n?\Z", trace) is None:
                return fail(trace, stderr_text)
        return fail(f"Твой код воняет. В следующий раз уложись в {MAX_MEMORY_BYTES // 1024 // 1024} МБ памяти.", stderr_text)
    except asyncio.TimeoutError:
        logger.error("Sandbox worker leaked after timeout")
        return fail("Молодец, сломал песочницу. This incident will be reported.", stderr.text())
    except eryx.EryxError as error:
        logger.warning(f"Sandbox worker failure: {error}")
        return fail("Молодец, сломал песочницу. This incident will be reported.", stderr.text())

    payload = sandbox_result.result if isinstance(sandbox_result.result, dict) else {}
    value = ""
    if (last_value := payload.get("last_value")) is not None:
        value = json.dumps(last_value, ensure_ascii=False)
    elif (last_value := payload.get("last_repr")) is not None:
        value = str(last_value)
    elif sandbox_result.result_error:
        logger.info(f"  Sandbox result not captured: {sandbox_result.result_error}")

    result = RunResult(ok=True, stdout=stdout.text(), stderr=stderr.text(), value=value)
    writes, result.write_error = _check_var_writes(payload.get("w", {}), stored_values.keys())
    previous_values: dict[str, int | None] = {}
    if writes and not result.write_error:
        previous_values = db.get().record_py_vars(writes)
        logger.info(f"  Applied {len(writes)} var writes")
    _remember_undo(trigger, previous_values, writes)
    return result


def format_reply(result: RunResult, get_key: str | None = None) -> str:
    def truncate(text: str, limit: int) -> str:
        suffix = "\n... (обрезано)"
        if len(escaped := html.escape(text)) <= limit:
            return escaped
        truncated = escaped[:max(0, limit - len(suffix))]
        return re.sub(r"&[^;]*$", "", truncated) + suffix  # drop HTML escape if truncated at the end

    def block(text: str, limit: int) -> str:
        body = truncate(text, limit)
        return f"<blockquote expandable>{body}</blockquote>" if len(text) > 500 or text.count("\n") > 5 else body

    reply = f"{get_key}\n" if get_key else ""
    reply += "🐍 " if result.ok else "🐍💀 "
    if result.value:
        reply += f"<code>{truncate(result.value, min(2000, 4000 - len(reply)))}</code>"
    if stdout := result.stdout.strip("\n"):
        reply += "" if reply.endswith(" ") else "\n"
        reply += block(stdout, min(2000, 4000 - len(reply)))
    if error := result.error.strip("\n"):
        reply += f"\n❌{block(error, min(2000, 4000 - len(reply)))}"
    if stderr := result.stderr.strip("\n"):
        reply += f"\n⚠️{block(stderr, min(2000, 4000 - len(reply)))}"
    if result.write_error:
        reply += f"\n⚠️{truncate(result.write_error, 250)}"
    return reply


_Undo = tuple[dict[str, int | None], dict[str, int], int | None]
_undo_by_user: dict[tuple[int, int], _Undo] = {}


def _remember_undo(trigger: CommandTrigger, previous: dict[str, int | None], written: dict[str, int]) -> None:
    _undo_by_user[(trigger.chat_id, trigger.user_id)] = (previous, written, None)


def _remember_undo_reply(trigger: CommandTrigger, reply_msg_id: int) -> None:
    if (undo := _undo_by_user.get((trigger.chat_id, trigger.user_id))) is not None:
        _undo_by_user[(trigger.chat_id, trigger.user_id)] = (*undo[:2], reply_msg_id)


async def handle_pyundo(update: Update, context: CallbackContext):
    if (message := update.effective_message) is None or message.from_user is None:
        return
    logger.info(f"[pyundo] {message.from_user.id}")

    if (undo := _undo_by_user.pop((message.chat_id, message.from_user.id), None)) is None:
        await message.reply_text("Что отменять-то собрался?", do_quote=True)
        return

    previous, written, reply_msg_id = undo
    db.get().record_py_vars(previous, expected=written)

    if reply_msg_id is not None:
        try:
            await context.bot.delete_message(message.chat_id, reply_msg_id)
        except TelegramError as error:
            logger.info(f"  Could not delete /py result {reply_msg_id}: {error}")

    await update.get_bot().set_message_reaction(message.chat_id, message.message_id, "👌")


_reply_by_command: dict[tuple[int, int], int] = {}


def _track_reply(chat_id: int, command_msg_id: int, reply_msg_id: int) -> None:
    if len(_reply_by_command) >= 500:
        del _reply_by_command[next(iter(_reply_by_command))]
    _reply_by_command[(chat_id, command_msg_id)] = reply_msg_id


def extract_code(text: str) -> str:
    match = re.match(r'/py(?:@\S+)?\s+(.+)', text.strip(), re.DOTALL)
    return match.group(1).strip() if match else ""


async def handle_py(update: Update, context: CallbackContext):
    if ((message := update.effective_message) is None or message.text is None
            or message.from_user is None):
        return
    logger.info(f"[py] {message.from_user.id}: {message.text}")

    if not (code := extract_code(message.text)):
        await message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML, do_quote=True)
        return

    trigger = CommandTrigger.from_update(update)
    if (result := await run_code(code, trigger)) is None:
        return
    response = format_reply(result)

    reply_key = (message.chat_id, message.message_id)
    if (update.edited_message is not None and (reply_msg_id := _reply_by_command.get(reply_key)) is not None):
        try:
            await context.bot.edit_message_text(
                response,
                chat_id=message.chat_id,
                message_id=reply_msg_id,
                parse_mode=ParseMode.HTML,
            )
            _remember_undo_reply(trigger, reply_msg_id)
        except TelegramError as error:
            logger.info(f"  Could not edit reply {reply_msg_id}: {error}")
        return

    reply = await message.reply_text(response, parse_mode=ParseMode.HTML)
    _track_reply(message.chat_id, message.message_id, reply.message_id)
    _remember_undo_reply(trigger, reply.message_id)


async def run_stored_script(bot: Bot, trigger: CommandTrigger, key: str, code: str) -> None:
    logger.info(f"[py] Running /get {key}")
    if (result := await run_code(code, trigger)) is None:
        return
    reply = await bot.send_message(
        trigger.chat_id,
        format_reply(result, get_key=key),
        parse_mode=ParseMode.HTML,
    )
    _remember_undo_reply(trigger, reply.message_id)


def subscribe(application: Application) -> None:
    application.add_handler(CommandHandler("py", handle_py))
    application.add_handler(CommandHandler("pyundo", handle_pyundo))
