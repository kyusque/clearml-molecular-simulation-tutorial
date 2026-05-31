from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a ClearML Agent. ClearML's documented default config location is ~/clearml.conf; this repo helper also supports local/clearml.conf for in-repo runs."
    )
    parser.add_argument(
        "--queue",
        nargs="+",
        default=["default"],
        help="ClearML queue names to listen to, in priority order.",
    )
    parser.add_argument(
        "--config-file",
        type=Path,
        help="Path to clearml.conf. If omitted, this helper resolves in this order: CLEARML_CONFIG_FILE, local/clearml.conf, ~/clearml.conf. Note: ClearML's documented default location is ~/clearml.conf.",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Pipe the agent log to stdout/stderr.",
    )
    parser.add_argument(
        "--create-queue",
        action="store_true",
        help="Create the requested queues if they do not exist.",
    )
    parser.add_argument(
        "--cpu-only",
        action="store_true",
        help="Disable GPU access for tasks launched by the agent.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print agent queue/schedule status and exit.",
    )
    return parser.parse_args()


def resolve_clearml_config_file(config_file_arg: Path | None) -> Path:
    if config_file_arg is not None:
        return config_file_arg.expanduser().resolve()

    env_path = os.environ.get("CLEARML_CONFIG_FILE")
    if env_path:
        return Path(env_path).expanduser().resolve()

    # Repository convenience: prefer local/clearml.conf for direct in-repo runs.
    repo_local = (REPO_ROOT / "local" / "clearml.conf").resolve()
    if repo_local.exists():
        return repo_local

    # ClearML's documented default location.
    home_local = (Path.home() / "clearml.conf").resolve()
    if home_local.exists():
        return home_local

    return repo_local


def find_gamess_dir() -> Path | None:
    for env_name in ("CLEARML_GAMESS_DIR", "GAMESS_DIR"):
        env_value = os.environ.get(env_name)
        if env_value:
            gamess_dir = Path(env_value).expanduser().resolve()
            rungms_name = "rungms.bat" if os.name == "nt" else "rungms"
            if (gamess_dir / rungms_name).exists():
                return gamess_dir

    if os.name == "nt":
        windows_default = Path("C:/Users/Public/gamess-64")
        if (windows_default / "rungms.bat").exists():
            return windows_default

    rungms_path = shutil.which("rungms.bat" if os.name == "nt" else "rungms")
    if rungms_path:
        return Path(rungms_path).resolve().parent
    return None


def find_gamess_version(gamess_dir: Path) -> str | None:
    suffix = ".exe" if os.name == "nt" else ".x"
    for executable in sorted(gamess_dir.glob(f"gamess.*{suffix}")):
        version = executable.name.removeprefix("gamess.").removesuffix(suffix)
        if version:
            return version
    return None


def main() -> int:
    args = parse_args()
    config_file = resolve_clearml_config_file(args.config_file)

    if not config_file.exists():
        print(
            "ClearML config file not found. This helper checked CLEARML_CONFIG_FILE, local/clearml.conf, and ~/clearml.conf. "
            "ClearML's documented default location is ~/clearml.conf. "
            f"Resolved path: {config_file.as_posix()}",
            file=sys.stderr,
        )
        return 2

    env = os.environ.copy()
    env["CLEARML_CONFIG_FILE"] = str(config_file)
    gamess_dir = find_gamess_dir()
    if gamess_dir:
        env["CLEARML_GAMESS_DIR"] = str(gamess_dir)
        env.setdefault("GAMESS_DIR", str(gamess_dir))
        gamess_version = os.environ.get("CLEARML_GAMESS_VERSION") or os.environ.get("GAMESS_VERSION")
        if not gamess_version:
            gamess_version = find_gamess_version(gamess_dir)
        if gamess_version:
            env["CLEARML_GAMESS_VERSION"] = gamess_version
            env.setdefault("GAMESS_VERSION", gamess_version)
    else:
        gamess_version = None

    command = ["clearml-agent", "daemon", "--queue", *args.queue]
    if args.foreground:
        command.append("--foreground")
    if args.create_queue:
        command.append("--create-queue")
    if args.cpu_only:
        command.append("--cpu-only")
    if args.status:
        command.append("--status")

    print(f"CLEARML_CONFIG_FILE={config_file.as_posix()}", flush=True)
    if gamess_dir:
        print(f"CLEARML_GAMESS_DIR={gamess_dir.as_posix()}", flush=True)
        if gamess_version:
            print(f"CLEARML_GAMESS_VERSION={gamess_version}", flush=True)
    else:
        print("CLEARML_GAMESS_DIR was not set because rungms was not found.", flush=True)
    print(" ".join(command), flush=True)

    return subprocess.call(command, env=env, cwd=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
