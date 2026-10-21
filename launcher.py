"""Windows delivery bootstrap for IMAGE OBSERVER BUILD 02.3 (stdlib only)."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
ENV_DIR = ROOT / ".venv"
LOG = ROOT / "launcher.log"
INSTALL_LOG = ROOT / "install.log"
REQUIRED = ("app.py", "processor.py", "requirements.txt", "先读我.txt")
PYTHON_CHECK = "import sys,struct;sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)"
IMPORTS = {"gradio": "gradio", "opencv-python-headless": "cv2", "Pillow": "PIL", "numpy": "numpy"}


def message(text: str) -> None:
    print(text, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as stream:
            stream.write(text + "\n")
    except OSError:
        pass  # A read-only extraction folder must still show the useful error.


def environment_python(directory: Path = ENV_DIR) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def pinned_requirements(path: Path = ROOT / "requirements.txt") -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split("==")
        if len(parts) != 2 or not all(parts):
            raise RuntimeError("requirements.txt 需要使用项目提供的固定版本，请重新解压完整项目包。")
        result[parts[0]] = parts[1]
    return result


def is_supported_python(python: Path) -> bool:
    try:
        return subprocess.run([str(python), "-c", PYTHON_CHECK], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_environment() -> Path:
    python = environment_python()
    if python.exists() and is_supported_python(python):
        return python
    if ENV_DIR.exists():
        suffix = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = ROOT / (".venv-backup-" + suffix)
        try:
            ENV_DIR.rename(backup)
        except OSError as exc:
            raise RuntimeError("现有 .venv 无法使用且被占用。请关闭旧工具窗口后重试；不会删除旧环境。") from exc
        message(f"已保留旧环境：{backup.name}，正在创建 Python 3.12 环境。")
    else:
        message("首次运行：正在创建本项目专用的 .venv，无需管理员权限。")
    try:
        venv.EnvBuilder(with_pip=True).create(ENV_DIR)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("创建 .venv 失败。请将整个项目解压到可写的本地文件夹，例如桌面，再双击启动。") from exc
    if not is_supported_python(python):
        raise RuntimeError("虚拟环境创建后无法运行。请确认安装的是 Python 3.12 64-bit，详情见 launcher.log。")
    return python


def dependency_problem(python: Path) -> str | None:
    pins = pinned_requirements()
    code = (
        "import importlib,importlib.metadata,json,sys;"
        "pins=json.loads(sys.argv[1]);mods=json.loads(sys.argv[2]);"
        "bad=[n+'=='+v for n,v in pins.items() if importlib.metadata.version(n)!=v];"
        "[importlib.import_module(m) for m in mods.values()];"
        "print('版本不匹配: '+', '.join(bad) if bad else '依赖版本和导入正常');"
        "sys.exit(bool(bad))"
    )
    try:
        result = subprocess.run([str(python), "-c", code, json.dumps(pins), json.dumps(IMPORTS)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if result.returncode:
            return (result.stdout + result.stderr).strip()
        check = subprocess.run([str(python), "-m", "pip", "check"], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=120)
        return None if check.returncode == 0 else (check.stdout + check.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)


def run_logged(command: list[str], log_path: Path, *, env: dict | None = None) -> int:
    with log_path.open("a", encoding="utf-8") as output:
        output.write("\n--- " + datetime.now().isoformat(timespec="seconds") + " ---\n")
        with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
            try:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    output.write(line)
                    output.flush()
                return process.wait()
            except KeyboardInterrupt:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise


def ensure_dependencies(python: Path) -> None:
    problem = dependency_problem(python)
    if problem is None:
        message("依赖已就绪，跳过安装。")
        return
    message("首次安装或依赖需要修复：将联网下载 Python 依赖，通常需要几分钟，请勿关闭窗口。")
    with INSTALL_LOG.open("a", encoding="utf-8") as stream:
        stream.write(problem + "\n")
    # ensurepip is bundled with Python; it does not download Python or packages.
    pip = subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True)
    if pip.returncode and run_logged([str(python), "-m", "ensurepip", "--upgrade"], INSTALL_LOG):
        raise RuntimeError("无法初始化 pip。请重新安装 Python 3.12 并保留 pip / venv 选项，详情见 install.log。")
    command = [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--only-binary=:all:",
               "--upgrade", "--force-reinstall", "-r", str(ROOT / "requirements.txt")]
    if run_logged(command, INSTALL_LOG):
        raise RuntimeError("依赖安装失败。请检查网络连接或代理后再次双击启动；详细错误保存在 install.log。")
    remaining = dependency_problem(python)
    if remaining:
        with INSTALL_LOG.open("a", encoding="utf-8") as stream:
            stream.write(remaining + "\n")
        raise RuntimeError("依赖仍无法加载。请查看 install.log；若提示 DLL load failed，请安装微软 VC++ 2015–2022 x64 运行库后重试。")
    message("依赖安装完成；以后启动将自动跳过已正确安装的依赖。")


def choose_port(first: int = 7860, last: int = 7879) -> int:
    for port in range(first, last + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("7860–7879 端口均被占用。请关闭之前的工具窗口后重试。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMAGE OBSERVER · BUILD 02.3 Windows 启动工具")
    parser.add_argument("--check", action="store_true", help="只检查并准备环境，不启动网页")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        try:
            LOG.write_text("IMAGE OBSERVER · BUILD 02.3\n", encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("项目文件夹不可写。请将完整 ZIP 解压到桌面等本地文件夹，再双击启动。") from exc
        if sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
            raise RuntimeError("需要 Python 3.12 64-bit。请按先读我.txt 安装后再次双击启动工具.bat。")
        missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
        if missing:
            raise RuntimeError("项目文件不完整：请右键 ZIP → 全部解压后，再双击启动工具.bat。缺少：" + "、".join(missing))
        python = ensure_environment()
        ensure_dependencies(python)
        port = choose_port()
        message(f"检查通过：IMAGE OBSERVER · BUILD 02.3，http://127.0.0.1:{port}")
        if args.check:
            return 0
        if port != 7860:
            message(f"7860 端口已被占用，自动改用 {port}；请使用本次自动打开的新页面。")
        message("正在启动并打开浏览器。请确认页面顶部显示 IMAGE OBSERVER · BUILD 02.3。")
        message("使用期间请保持此窗口打开；按 Ctrl+C 停止工具。")
        env = dict(os.environ, PYTHONUTF8="1", GRADIO_ANALYTICS_ENABLED="False",
                   IMAGE_OBSERVER_PORT=str(port), IMAGE_OBSERVER_OPEN_BROWSER="1")
        code = run_logged([str(python), "-u", str(ROOT / "app.py")], LOG, env=env)
        if code:
            message("[启动失败] 请查看此窗口最后的错误，或同目录 launcher.log。")
        return code
    except KeyboardInterrupt:
        message("工具已停止。")
        return 0
    except Exception as exc:
        message("[启动失败] " + str(exc))
        message("请保留 launcher.log / install.log 以便排查；无需手动修改代码。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
