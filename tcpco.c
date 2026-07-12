// SPDX-License-Identifier: GPL-2.0
// tcpco.c - loader user-space: carrega o BPF, consome o ring buffer,
// imprime as métricas na tela e grava o CSV.
#include <argp.h>
#include <arpa/inet.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <bpf/libbpf.h>
#include "tcpco.skel.h"

struct flow_key {
    __u32 src_ip;
    __u32 dst_ip;
    __u16 src_port;
    __u16 dst_port;
};

struct tcp_metrics {
    __u32 snd_cwnd;
    __u32 ssthresh;
    __u32 srtt;
    __u32 retransmissions;
    __u32 duplicate_acks;
    __u64 bytes_acked;
    __u32 ca_state;
    __u64 ts_ns;
};

struct event {
    struct flow_key key;
    struct tcp_metrics m;
};

static const char *ca_state_str(__u32 s) {
    switch (s) {
    case 0: return "Open";
    case 1: return "Disorder";
    case 2: return "CWR";
    case 3: return "Recovery";
    case 4: return "Loss";
    default: return "?";
    }
}

static volatile int exiting = 0;
static void on_sigint(int sig) { exiting = 1; }

static FILE *csv;
static __u64 t0_ns = 0;

static int handle_event(void *ctx, void *data, size_t len) {
    struct event *e = data;
    if (t0_ns == 0) t0_ns = e->m.ts_ns;
    double t = (e->m.ts_ns - t0_ns) / 1e9;

    char s[16], d[16];
    inet_ntop(AF_INET, &e->key.src_ip, s, sizeof(s));
    inet_ntop(AF_INET, &e->key.dst_ip, d, sizeof(d));

    printf("%8.3f  %s:%u -> %s:%u  cwnd=%u ssth=%u srtt=%uus retr=%u inflight=%u acked=%llu %s\n",
           t, s, e->key.src_port, d, e->key.dst_port,
           e->m.snd_cwnd, e->m.ssthresh, e->m.srtt, e->m.retransmissions,
           e->m.duplicate_acks, (unsigned long long)e->m.bytes_acked,
           ca_state_str(e->m.ca_state));

    if (csv) {
        fprintf(csv, "%.6f,%s,%u,%s,%u,%u,%u,%u,%u,%u,%llu,%s\n",
                t, s, e->key.src_port, d, e->key.dst_port,
                e->m.snd_cwnd, e->m.ssthresh, e->m.srtt, e->m.retransmissions,
                e->m.duplicate_acks, (unsigned long long)e->m.bytes_acked,
                ca_state_str(e->m.ca_state));
        fflush(csv);
    }
    return 0;
}

int main(int argc, char **argv) {
    const char *csv_path = argc > 1 ? argv[1] : "tcpco.csv";
    struct tcpco_bpf *skel;
    struct ring_buffer *rb = NULL;
    int err;

    libbpf_set_strict_mode(LIBBPF_STRICT_ALL);
    skel = tcpco_bpf__open_and_load();
    if (!skel) { fprintf(stderr, "erro ao abrir/carregar BPF\n"); return 1; }

    err = tcpco_bpf__attach(skel);
    if (err) { fprintf(stderr, "erro ao anexar (rode como root?)\n"); goto cleanup; }

    rb = ring_buffer__new(bpf_map__fd(skel->maps.events), handle_event, NULL, NULL);
    if (!rb) { fprintf(stderr, "erro no ring buffer\n"); goto cleanup; }

    csv = fopen(csv_path, "w");
    if (csv)
        fprintf(csv, "t,src_ip,src_port,dst_ip,dst_port,cwnd,ssthresh,srtt_us,"
                     "retrans,inflight,bytes_acked,ca_state\n");

    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);
    printf("TCP-CO ativo. CSV: %s  (Ctrl-C para sair)\n", csv_path);

    while (!exiting) {
        err = ring_buffer__poll(rb, 200 /*ms*/);
        if (err == -EINTR) { err = 0; break; }
        if (err < 0) { fprintf(stderr, "poll: %d\n", err); break; }
    }

cleanup:
    if (csv) fclose(csv);
    ring_buffer__free(rb);
    tcpco_bpf__destroy(skel);
    return err ? 1 : 0;
}