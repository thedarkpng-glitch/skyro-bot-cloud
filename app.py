import os
import re
import io
import json
import time
import uuid
import shutil
import zipfile
import secrets
import hashlib
import sqlite3
import platform
import subprocess
from pathlib import Path
from datetime import datetime

import psutil
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, send_file
)
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
BOTS_DIR = BASE / "bots"
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "panel.sqlite3"
CONFIG_PATH = DATA_DIR / "config.json"

BOTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("PANEL_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

processes = {}  # bot_id -> Popen


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            runtime TEXT NOT NULL,
            entrypoint TEXT NOT NULL DEFAULT '',
            python_exec TEXT DEFAULT '',
            node_exec TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS envs (
            bot_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY(bot_id, key)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            action TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_event(action, message, level="info"):
    con = db()
    con.execute(
        "INSERT INTO logs(level, action, message, created_at) VALUES(?,?,?,?)",
        (level, action, message, now())
    )
    con.commit()
    con.close()


def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    password = secrets.token_urlsafe(10)
    cfg = {
        "admin_password": password,
        "panel_name": "Skyro Bot Cloud",
        "created": now()
    }
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("\n========================================")
    print(" SENHA ADMINISTRATIVA INICIAL")
    print("========================================")
    print(password)
    print("Guarde essa senha e altere data/config.json.")
    print("========================================\n")
    return cfg


CONFIG = load_config()
init_db()


def require_login():
    return session.get("logged_in") is True


def require_admin():
    return session.get("admin") is True


def bot_row(bot_id):
    con = db()
    row = con.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone()
    con.close()
    return row


def bot_dir(bot_id):
    return BOTS_DIR / bot_id


def safe_path(bot_id, rel):
    base = bot_dir(bot_id).resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        raise ValueError("Caminho inválido.")
    return target


def detect_runtimes():
    result = {"python": [], "node": []}

    try:
        out = subprocess.check_output(
            ["py", "-0p"], text=True, stderr=subprocess.STDOUT, timeout=5
        )
        for line in out.splitlines():
            m = re.search(r"(-\d+(?:\.\d+)?)\s+(.+)$", line.strip())
            if m:
                result["python"].append({
                    "version": m.group(1).lstrip("-"),
                    "path": m.group(2).strip()
                })
    except Exception:
        pass

    for cmd in ["python", "python3"]:
        try:
            p = subprocess.run(
                [cmd, "--version"], capture_output=True, text=True, timeout=5
            )
            if p.returncode == 0:
                ver = (p.stdout or p.stderr).strip()
                result["python"].append({"version": ver, "path": cmd})
        except Exception:
            pass

    for cmd in ["node"]:
        try:
            p = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
            if p.returncode == 0:
                result["node"].append({"version": p.stdout.strip(), "path": cmd})
        except Exception:
            pass

    # Remove duplicados.
    for k in result:
        seen = set()
        result[k] = [
            x for x in result[k]
            if not (x["path"] in seen or seen.add(x["path"]))
        ]
    return result


def is_running(bot_id):
    p = processes.get(bot_id)
    return bool(p and p.poll() is None)


def command_for_bot(row):
    runtime = row["runtime"]
    entry = row["entrypoint"].strip()

    if runtime == "python":
        executable = row["python_exec"] or "python"
        return [executable, entry]

    executable = row["node_exec"] or "node"
    return [executable, entry]


def start_bot_process(row):
    bot_id = row["id"]
    if is_running(bot_id):
        return False, "Bot já está online."

    directory = bot_dir(bot_id)
    entry = row["entrypoint"].strip()

    if not entry:
        return False, "Defina o arquivo de entrada em Configs."

    target = safe_path(bot_id, entry)
    if not target.exists():
        return False, f"Arquivo de entrada não encontrado: {entry}"

    cmd = command_for_bot(row)

    env = os.environ.copy()
    con = db()
    env_rows = con.execute(
        "SELECT key,value FROM envs WHERE bot_id=?", (bot_id,)
    ).fetchall()
    con.close()

    for r in env_rows:
        env[r["key"]] = r["value"]

    stdout_file = open(directory / "console.log", "a", encoding="utf-8", buffering=1)
    stdout_file.write(f"\n\n[{now()}] START: {' '.join(cmd)}\n")

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    p = subprocess.Popen(
        cmd,
        cwd=str(directory),
        stdout=stdout_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=creationflags
    )

    processes[bot_id] = p
    log_event("Bot iniciado", f"{row['name']} iniciado com PID {p.pid}.")
    return True, f"Bot iniciado. PID {p.pid}"


def stop_bot_process(bot_id):
    p = processes.get(bot_id)
    if not p or p.poll() is not None:
        return False, "Bot já está offline."

    try:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
        log_event("Bot parado", f"Bot {bot_id} foi parado.")
        return True, "Bot parado."
    except Exception as e:
        return False, str(e)


def restart_bot_process(row):
    stop_bot_process(row["id"])
    time.sleep(0.5)
    return start_bot_process(row)


@app.route("/")
def index():
    if not require_login():
        return redirect(url_for("login"))
    return render_template("index.html", panel_name=CONFIG.get("panel_name", "Bot Panel"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if secrets.compare_digest(password, CONFIG.get("admin_password", "")):
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Senha incorreta.")
    return render_template("login.html", error="")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/api/system")
def api_system():
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401

    vm = {
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_total_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        "disk_percent": psutil.disk_usage(str(BASE)).percent,
        "disk_free_gb": round(psutil.disk_usage(str(BASE)).free / 1024**3, 1),
        "uptime": int(time.time() - psutil.boot_time())
    }
    return jsonify(vm)


@app.get("/api/runtimes")
def api_runtimes():
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(detect_runtimes())


@app.get("/api/bots")
def api_bots():
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401

    con = db()
    rows = con.execute("SELECT * FROM bots ORDER BY created_at DESC").fetchall()
    con.close()

    data = []
    for r in rows:
        item = dict(r)
        item["status"] = "online" if is_running(r["id"]) else "offline"
        if r["id"] in processes and processes[r["id"]].poll() is not None:
            item["exit_code"] = processes[r["id"]].returncode
        data.append(item)
    return jsonify(data)


@app.post("/api/bots")
def create_bot():
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401

    name = request.form.get("name", "").strip()
    runtime = request.form.get("runtime", "").strip().lower()
    entrypoint = request.form.get("entrypoint", "").strip()
    upload = request.files.get("zip")

    if not name:
        return jsonify({"error": "Nome obrigatório."}), 400
    if runtime not in ("python", "node"):
        return jsonify({"error": "Runtime inválido."}), 400

    bot_id = uuid.uuid4().hex[:12]
    directory = bot_dir(bot_id)
    directory.mkdir(parents=True, exist_ok=True)

    if upload and upload.filename:
        filename = secure_filename(upload.filename)
        if not filename.lower().endswith(".zip"):
            shutil.rmtree(directory, ignore_errors=True)
            return jsonify({"error": "Envie um ZIP."}), 400

        data = upload.read()
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for member in z.infolist():
                    # Proteção contra Zip Slip.
                    destination = (directory / member.filename).resolve()
                    if directory.resolve() not in destination.parents and destination != directory.resolve():
                        raise ValueError("ZIP contém caminho inválido.")
                z.extractall(directory)
        except Exception as e:
            shutil.rmtree(directory, ignore_errors=True)
            return jsonify({"error": f"ZIP inválido: {e}"}), 400

    con = db()
    con.execute(
        "INSERT INTO bots(id,name,runtime,entrypoint,python_exec,node_exec,created_at,updated_at)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (bot_id, name, runtime, entrypoint, "", "", now(), now())
    )
    con.commit()
    con.close()

    log_event("Bot criado", f"{name} ({runtime}) foi criado.")
    return jsonify({"ok": True, "id": bot_id})


@app.delete("/api/bots/<bot_id>")
def delete_bot(bot_id):
    if not require_admin():
        return jsonify({"error": "admin_required"}), 403

    row = bot_row(bot_id)
    if not row:
        return jsonify({"error": "Bot não encontrado."}), 404

    stop_bot_process(bot_id)
    con = db()
    con.execute("DELETE FROM envs WHERE bot_id=?", (bot_id,))
    con.execute("DELETE FROM bots WHERE id=?", (bot_id,))
    con.commit()
    con.close()

    shutil.rmtree(bot_dir(bot_id), ignore_errors=True)
    log_event("Bot excluído", f"{row['name']} foi excluído.", "warning")
    return jsonify({"ok": True})


@app.post("/api/bots/<bot_id>/action")
def bot_action(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401

    row = bot_row(bot_id)
    if not row:
        return jsonify({"error": "Bot não encontrado."}), 404

    action = request.json.get("action", "")
    if action == "start":
        ok, msg = start_bot_process(row)
    elif action == "stop":
        ok, msg = stop_bot_process(bot_id)
    elif action == "restart":
        ok, msg = restart_bot_process(row)
    else:
        return jsonify({"error": "Ação inválida."}), 400

    return jsonify({"ok": ok, "message": msg})


@app.get("/api/bots/<bot_id>/files")
def list_files(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401
    if not bot_row(bot_id):
        return jsonify({"error": "Bot não encontrado."}), 404

    base = bot_dir(bot_id)
    items = []
    for p in sorted(base.rglob("*")):
        if p.name == "console.log":
            continue
        rel = p.relative_to(base).as_posix()
        items.append({
            "path": rel,
            "type": "folder" if p.is_dir() else "file"
        })
    return jsonify(items)


@app.get("/api/bots/<bot_id>/file")
def read_file(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401
    rel = request.args.get("path", "")
    try:
        p = safe_path(bot_id, rel)
        if not p.exists() or not p.is_file():
            return jsonify({"error": "Arquivo não encontrado."}), 404
        if p.stat().st_size > 2 * 1024 * 1024:
            return jsonify({"error": "Arquivo muito grande para o editor."}), 400
        return jsonify({"path": rel, "content": p.read_text(encoding="utf-8", errors="replace")})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/bots/<bot_id>/file")
def write_file(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    rel = data.get("path", "")
    content = data.get("content", "")

    if not rel:
        return jsonify({"error": "Caminho obrigatório."}), 400
    try:
        p = safe_path(bot_id, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        log_event("Arquivo salvo", f"{bot_id}: {rel}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/bots/<bot_id>/console")
def console(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401
    p = bot_dir(bot_id) / "console.log"
    if not p.exists():
        return jsonify({"content": ""})
    content = p.read_text(encoding="utf-8", errors="replace")
    return jsonify({"content": content[-50000:]})


@app.post("/api/bots/<bot_id>/console")
def console_command(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401

    row = bot_row(bot_id)
    if not row:
        return jsonify({"error": "Bot não encontrado."}), 404

    command = request.json.get("command", "").strip()
    if not command:
        return jsonify({"error": "Comando vazio."}), 400

    lower = command.lower()

    if lower == "shutdown":
        ok, msg = stop_bot_process(bot_id)
        return jsonify({"ok": ok, "message": msg})

    if lower == "restart":
        ok, msg = restart_bot_process(row)
        return jsonify({"ok": ok, "message": msg})

    # Comandos são executados no diretório do bot.
    # Para produção pública, troque isto por uma whitelist/sandbox.
    try:
        proc = subprocess.run(
            command,
            cwd=str(bot_dir(bot_id)),
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        with open(bot_dir(bot_id) / "console.log", "a", encoding="utf-8") as f:
            f.write(f"\n$ {command}\n{output}\n")
        return jsonify({
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "output": output[-20000:]
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "output": "Comando excedeu 120 segundos."}), 400
    except Exception as e:
        return jsonify({"ok": False, "output": str(e)}), 400


@app.get("/api/bots/<bot_id>/config")
def get_config(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401
    row = bot_row(bot_id)
    if not row:
        return jsonify({"error": "Bot não encontrado."}), 404

    con = db()
    envs = con.execute(
        "SELECT key,value FROM envs WHERE bot_id=? ORDER BY key", (bot_id,)
    ).fetchall()
    con.close()

    return jsonify({
        "entrypoint": row["entrypoint"],
        "python_exec": row["python_exec"],
        "node_exec": row["node_exec"],
        "env": [{"key": x["key"], "value": x["value"]} for x in envs]
    })


@app.post("/api/bots/<bot_id>/config")
def save_config(bot_id):
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401

    row = bot_row(bot_id)
    if not row:
        return jsonify({"error": "Bot não encontrado."}), 404

    data = request.get_json(force=True)
    entrypoint = data.get("entrypoint", "").strip()
    python_exec = data.get("python_exec", "").strip()
    node_exec = data.get("node_exec", "").strip()
    env = data.get("env", [])

    # Impede usar caminho de entrada fora da pasta do bot.
    try:
        if entrypoint:
            safe_path(bot_id, entrypoint)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    con = db()
    con.execute(
        "UPDATE bots SET entrypoint=?,python_exec=?,node_exec=?,updated_at=? WHERE id=?",
        (entrypoint, python_exec, node_exec, now(), bot_id)
    )
    con.execute("DELETE FROM envs WHERE bot_id=?", (bot_id,))
    for item in env:
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", ""))
        if key and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            con.execute(
                "INSERT INTO envs(bot_id,key,value) VALUES(?,?,?)",
                (bot_id, key, value)
            )
    con.commit()
    con.close()

    log_event("Configuração atualizada", f"Bot {row['name']} foi configurado.")
    return jsonify({"ok": True})


@app.post("/api/admin/login")
def admin_login():
    if not require_login():
        return jsonify({"error": "unauthorized"}), 401
    password = request.json.get("password", "")
    if secrets.compare_digest(password, CONFIG.get("admin_password", "")):
        session["admin"] = True
        return jsonify({"ok": True})
    return jsonify({"error": "Senha administrativa incorreta."}), 403


@app.get("/api/admin/logs")
def admin_logs():
    if not require_admin():
        return jsonify({"error": "admin_required"}), 403
    con = db()
    rows = con.execute(
        "SELECT * FROM logs ORDER BY id DESC LIMIT 100"
    ).fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/admin/status")
def admin_status():
    if not require_admin():
        return jsonify({"error": "admin_required"}), 403

    con = db()
    total = con.execute("SELECT COUNT(*) c FROM bots").fetchone()["c"]
    con.close()
    online = sum(1 for k in processes if is_running(k))

    return jsonify({
        "total_bots": total,
        "online_bots": online,
        "admin": True,
        "host": platform.node()
    })


@app.get("/api/admin/files")
def admin_files():
    if not require_admin():
        return jsonify({"error": "admin_required"}), 403
    return jsonify({
        "bots_dir": str(BOTS_DIR),
        "hostname": platform.node(),
        "os": platform.platform()
    })


if __name__ == "__main__":
    print("Starting Bot Host Panel...")
    app.run(host="127.0.0.1", port=5000, debug=False)
