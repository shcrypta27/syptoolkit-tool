#!/usr/bin/env python3
"""
SYPTOOLKIT — main menu launcher
"""
import os, sys, subprocess, platform

RED    = "\033[91m"
YEL    = "\033[93m"
CYN    = "\033[96m"
GRN    = "\033[92m"
MAG    = "\033[95m"
WHT    = "\033[97m"
DIM    = "\033[2m"
RST    = "\033[0m"
BOLD   = "\033[1m"

LOGO = f"""{RED}
   _______ ___ ___ _______ _______ _______ _______ ___     ___ ___  ___ _______ 
  |   _   |   Y   |   _   |       |   _   |   _   |   |   |   Y   )|   |       |
  |   1___|   1   |.  1   |.|   | |.  |   |.  |   |.  |   |.  1  / |.  |.|   | |
  |____   |\_   _/|.  ____`-|.  |-|.  |   |.  |   |.  |___|.  _  \ |.  `-|.  |-'
  |:  1   | |:  | |:  |     |:  | |:  1   |:  1   |:  1   |:  |   \|:  | |:  |  
  |::.. . | |::.| |::.|     |::.| |::.. . |::.. . |::.. . |::.| .  |::.| |::.|  
  `-------' `---' `---'     `---' `-------`-------`-------`--- ---'`---' `---'     {RST}
{DIM}                         [ offensive security toolkit v1.0 ]{RST}
"""

MENU = f"""
{YEL}┌─────────────────────────────────────────────────────┐
│                   {WHT}TOOL SELECTION{YEL}                      │
├─────────────────────────────────────────────────────┤
│  {CYN}[1]{YEL} RAT — Android          {DIM}(Python / Java){YEL}          │
│  {CYN}[2]{YEL} RAT — Linux            {DIM}(Python){YEL}                 │
│  {CYN}[3]{YEL} RAT — Windows          {DIM}(Python / PowerShell){YEL}    │
│  {CYN}[4]{YEL} DOS Attack Tool        {DIM}(C){YEL}                      │
│  {CYN}[5]{YEL} Camera Hack Suite      {DIM}(Python / Bash){YEL}          │
│  {CYN}[0]{YEL} Exit                                         │
└─────────────────────────────────────────────────────┘{RST}
"""

TOOLS = {
    "1": ("rat_android/menu.py",   "python3"),
    "2": ("rat_linux/menu.py",     "python3"),
    "3": ("rat_windows/menu.py",   "python3"),
    "4": ("dos/menu.py",           "python3"),
    "5": ("camera/menu.py",        "python3"),
}

def clear(): os.system("cls" if platform.system() == "Windows" else "clear")

def main():
    while True:
        clear()
        print(LOGO)
        print(MENU)
        choice = input(f"{RED}syptoolkit{RST} {YEL}>{RST} ").strip()
        if choice == "0":
            print(f"\n{DIM}session closed.{RST}\n")
            sys.exit(0)
        if choice in TOOLS:
            script, interp = TOOLS[choice]
            path = os.path.join(os.path.dirname(__file__), script)
            if os.path.exists(path):
                subprocess.run([interp, path])
            else:
                input(f"{RED}[!] tool not found: {path}{RST}  [enter]")
        else:
            input(f"{YEL}[?] invalid choice — press enter{RST}")

if __name__ == "__main__":
    main()
