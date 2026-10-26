# SYPTOOLKIT

multi-language offensive security toolkit

## launch
```bash
python3 menu.py
```

## structure
```
syptoolkit/
├── menu.py                        Python   main menu
├── rat_android/
│   ├── menu.py                    Python   Android RAT menu
│   └── RatService.java            Java     Android background service
├── rat_linux/
│   └── menu.py                    Python   Linux RAT + C2 + one-liners
├── rat_windows/
│   ├── menu.py                    Python   Windows RAT menu
│   └── keylog_persist.ps1         PowerShell  keylogger + persistence
├── dos/
│   ├── menu.py                    Python   DoS menu
│   └── dos_tool.c                 C        UDP/SYN/ICMP/HTTP flood (compile first)
└── camera/
    ├── menu.py                    Python   camera hack menu
    └── cam_scan.sh                Bash     nmap + ffprobe camera scanner
```

## deps

| tool           | install                              |
|----------------|--------------------------------------|
| python3        | pre-installed on most Linux          |
| msfvenom       | metasploit-framework                 |
| msfconsole     | metasploit-framework                 |
| adb            | android-tools-adb                    |
| ffmpeg/ffprobe | apt install ffmpeg                   |
| nmap           | apt install nmap                     |
| gcc            | apt install gcc (for dos_tool.c)     |
| opencv-python  | pip3 install opencv-python           |
| pynput         | pip3 install pynput                  |
| shodan         | pip3 install shodan                  |

## build C dos tool
```bash
cd dos
gcc -O2 -pthread -o dos_tool dos_tool.c
```

## notes
- SYN + ICMP flood require root (raw sockets)
- Android Java service: integrate into APK with Android Studio; set C2_HOST in RatService.java
- PowerShell scripts: run with `-ExecutionPolicy Bypass`
- all loot saved to `loot/` directory
