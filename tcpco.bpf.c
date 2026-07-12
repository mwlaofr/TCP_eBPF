// Coleta métricas de congestionamento por fluxo via kprobe em tcp_rcv_established
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

char LICENSE[] SEC("license") = "GPL";

#define AF_INET 2

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
    __u32 retransmissions; // retransmissoes
    __u32 duplicate_acks;
    __u64 bytes_acked;
    __u32 ca_state; // estado Open/Disorder/CWR/Recovery/Loss
    __u64 ts_ns; // timestamp
};

// mapa eBPF por conexão
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 65536);
    __type(key, struct flow_key);
    __type(value, struct tcp_metrics);
} flows SEC(".maps");

// ring buffer para stream em tempo real ao user-space
struct event {
    struct flow_key key;
    struct tcp_metrics m;
};

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 20); // 1 MB
} events SEC(".maps");

SEC("kprobe/tcp_rcv_established")
int BPF_KPROBE(handle_tcp_rcv, struct sock *sk)
{
    if (!sk)
        return 0;

    // So IPv4
    __u16 family = BPF_CORE_READ(sk, __sk_common.skc_family);
    if (family != AF_INET)
        return 0;

    struct flow_key key = {};
    key.src_ip   = BPF_CORE_READ(sk, __sk_common.skc_rcv_saddr);
    key.dst_ip   = BPF_CORE_READ(sk, __sk_common.skc_daddr);
    key.src_port = BPF_CORE_READ(sk, __sk_common.skc_num);           
    key.dst_port = bpf_ntohs(BPF_CORE_READ(sk, __sk_common.skc_dport));

    // tcp_sock herda de inet_connection_sock que herda de sock.
    struct tcp_sock *tp = (struct tcp_sock *)sk;
    struct inet_connection_sock *icsk = (struct inet_connection_sock *)sk;

    struct tcp_metrics m = {};
    // Em kernels ~5.10+ snd_cwnd virou bitfield; ler com _BITFIELD_PROBED e portavel.
    m.snd_cwnd        = BPF_CORE_READ_BITFIELD_PROBED(tp, snd_cwnd);
    m.ssthresh        = BPF_CORE_READ(tp, snd_ssthresh);
    m.srtt            = BPF_CORE_READ(tp, srtt_us) >> 3;
    m.retransmissions = BPF_CORE_READ(tp, total_retrans);
    m.duplicate_acks  = BPF_CORE_READ(tp, packets_out);
    m.bytes_acked     = BPF_CORE_READ(tp, bytes_acked);
    m.ca_state        = BPF_CORE_READ_BITFIELD_PROBED(icsk, icsk_ca_state);
    m.ts_ns           = bpf_ktime_get_ns();

    bpf_map_update_elem(&flows, &key, &m, BPF_ANY);

    struct event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);
    if (e) {
        e->key = key;
        e->m   = m;
        bpf_ringbuf_submit(e, 0);
    }
    return 0;
}