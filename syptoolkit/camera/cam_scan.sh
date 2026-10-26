#!/usr/bin/env bash
# cam_scan.sh — fast camera scanner using nmap + banner grabs
# usage: ./cam_scan.sh <subnet> (e.g. 192.168.1.0/24)

RED='\033[91m'; YEL='\033[93m'; GRN='\033[92m'; DIM='\033[2m'; RST='\033[0m'

SUBNET=${1:-"192.168.1.0/24"}
OUTDIR="loot/camera"
mkdir -p "$OUTDIR"

echo -e "\n${RED}[SYPTOOLKIT]${RST} ${YEL}Camera Scanner${RST}"
echo -e "${DIM}target: $SUBNET${RST}\n"

# ── port scan ─────────────────────────────────────────────────────────────────
if ! command -v nmap &>/dev/null; then
    echo -e "${RED}[!] nmap not found — install with: apt install nmap${RST}"; exit 1
fi

echo -e "${DIM}[*] scanning ports 80,554,8080,8554,37777,34567,9000...${RST}"
nmap -p 80,554,8080,8554,37777,34567,9000 --open -T4 \
     --script http-title,rtsp-url-brute \
     -oN "$OUTDIR/nmap_cameras.txt" "$SUBNET" 2>/dev/null

echo -e "${GRN}[+] nmap results saved: $OUTDIR/nmap_cameras.txt${RST}"

# ── grep cameras from nmap output ─────────────────────────────────────────────
echo -e "\n${YEL}[*] extracting open hosts...${RST}"
grep -E "Nmap scan report|open" "$OUTDIR/nmap_cameras.txt" | \
    grep -v "^#" > "$OUTDIR/open_hosts.txt"

# ── RTSP path bruteforce with ffprobe ────────────────────────────────────────
RTSP_PATHS=(
    "/" "/live" "/live/ch0" "/h264/ch1/main/av_stream"
    "/cam/realmonitor?channel=1&subtype=0"
    "/streaming/channels/1" "/video1"
)

probe_rtsp() {
    local ip=$1 port=${2:-554}
    for path in "${RTSP_PATHS[@]}"; do
        url="rtsp://$ip:$port$path"
        if ffprobe -v quiet -rtsp_transport tcp -i "$url" &>/dev/null 2>&1; then
            echo -e "  ${GRN}[+] RTSP alive: $url${RST}"
            echo "$url" >> "$OUTDIR/live_rtsp.txt"
            return 0
        fi
    done
}

if command -v ffprobe &>/dev/null; then
    echo -e "\n${YEL}[*] probing RTSP streams...${RST}"
    while IFS= read -r line; do
        if [[ "$line" =~ ^Nmap\ scan\ report\ for\ (.+)$ ]]; then
            current_ip="${BASH_REMATCH[1]}"
        fi
        if [[ "$line" =~ 554.*open ]]; then
            probe_rtsp "$current_ip" 554 &
        fi
        if [[ "$line" =~ 8554.*open ]]; then
            probe_rtsp "$current_ip" 8554 &
        fi
    done < "$OUTDIR/nmap_cameras.txt"
    wait
else
    echo -e "${DIM}  ffprobe not found — skipping RTSP probe${RST}"
fi

# ── HTTP cam check ────────────────────────────────────────────────────────────
echo -e "\n${YEL}[*] checking HTTP camera interfaces...${RST}"
grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' "$OUTDIR/nmap_cameras.txt" | sort -u | while read ip; do
    for port in 80 8080; do
        title=$(curl -sk --max-time 3 "http://$ip:$port/" | grep -oi '<title>[^<]*' | sed 's/<title>//i')
        if echo "$title" | grep -qiE "camera|webcam|ipcam|nvr|dvr|dahua|hikvision|axis|cctv"; then
            echo -e "  ${GRN}[+] HTTP CAM: http://$ip:$port  [$title]${RST}"
            echo "http://$ip:$port  $title" >> "$OUTDIR/http_cams.txt"
        fi
    done
done

echo -e "\n${GRN}[+] scan complete — results in $OUTDIR/${RST}\n"
