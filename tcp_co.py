from bcc import BPF
import socket
import struct
import csv

BPF_PROGRAM = r"""
#include <uapi/linux/ptrace.h>

struct event_t {
    u32 src_ip;
    u32 dst_ip;
    u16 sport;
    u16 dport;
    u32 cwnd;
    u32 ssthresh;
    u32 srtt;
    u32 snd_wnd;
    u32 rcv_wnd;
    u64 bytes_acked;
    u32 retrans;
    u8  oldstate;
    u8  newstate;
    u64 timestamp;
    char ca_name[16];
};

BPF_PERF_OUTPUT(events);
BPF_HASH(retrans_count, u64, u32);

// Tracepoint 1: mudancas de estado TCP (conexoes, fechamentos)
TRACEPOINT_PROBE(sock, inet_sock_set_state) {
    if (args->protocol != 6) return 0;

    struct event_t evt = {};
    __builtin_memcpy(&evt.src_ip, args->saddr, 4);
    __builtin_memcpy(&evt.dst_ip, args->daddr, 4);
    evt.sport    = args->sport;
    evt.dport    = args->dport;
    evt.oldstate = args->oldstate;
    evt.newstate = args->newstate;
    evt.timestamp = bpf_ktime_get_ns();
    events.perf_submit(args, &evt, sizeof(evt));
    return 0;
}

// Tracepoint 2: metricas TCP (cwnd, ssthresh, srtt, etc)
TRACEPOINT_PROBE(tcp, tcp_probe) {
    struct event_t evt = {};
    __builtin_memcpy(&evt.src_ip, args->saddr, 4);
    __builtin_memcpy(&evt.dst_ip, args->daddr, 4);
    evt.sport      = args->sport;
    evt.dport      = args->dport;
    evt.cwnd       = args->snd_cwnd;
    evt.ssthresh   = args->snd_wnd;
    evt.srtt       = args->srtt;
    evt.snd_wnd    = args->snd_wnd;
    evt.rcv_wnd    = args->rcv_wnd;
    evt.bytes_acked = args->data_len;
    evt.oldstate   = 255;  // marcador: evento de metrica
    evt.newstate   = 255;
    evt.timestamp  = bpf_ktime_get_ns();
    events.perf_submit(args, &evt, sizeof(evt));
    return 0;
}

// Tracepoint 3: retransmissoes
TRACEPOINT_PROBE(tcp, tcp_retransmit_skb) {
    struct event_t evt = {};
    __builtin_memcpy(&evt.src_ip, args->saddr, 4);
    __builtin_memcpy(&evt.dst_ip, args->daddr, 4);
    evt.sport     = args->sport;
    evt.dport     = args->dport;
    evt.oldstate  = 254;  // marcador: evento de retransmissao
    evt.newstate  = 254;
    evt.timestamp = bpf_ktime_get_ns();
    events.perf_submit(args, &evt, sizeof(evt));
    return 0;
}
"""

# ── structs Python ──────────────────────────────

import ctypes as ct

class EventT(ct.Structure):
    _fields_ = [
        ("src_ip",     ct.c_uint32),
        ("dst_ip",     ct.c_uint32),
        ("sport",      ct.c_uint16),
        ("dport",      ct.c_uint16),
        ("cwnd",       ct.c_uint32),
        ("ssthresh",   ct.c_uint32),
        ("srtt",       ct.c_uint32),
        ("snd_wnd",    ct.c_uint32),
        ("rcv_wnd",    ct.c_uint32),
        ("bytes_acked",ct.c_uint64),
        ("retrans",    ct.c_uint32),
        ("oldstate",   ct.c_uint8),
        ("newstate",   ct.c_uint8),
        ("timestamp",  ct.c_uint64),
        ("ca_name",    ct.c_char * 16),
    ]

TCP_STATES = {
    1: "ESTABLISHED", 2: "SYN_SENT",   3: "SYN_RECV",
    4: "FIN_WAIT1",   5: "FIN_WAIT2",  6: "TIME_WAIT",
    7: "CLOSE",       8: "CLOSE_WAIT", 9: "LAST_ACK",
    10: "LISTEN",     11: "CLOSING",
}

def ip4(raw):
    return socket.inet_ntoa(struct.pack("I", raw))

def fmt_flow(e):
    return f"{ip4(e.src_ip)}:{e.sport} -> {ip4(e.dst_ip)}:{e.dport}"

# ── CSV ─────────────────────────────────────────

CSV_FILE = "tcp_metrics.csv"
csv_file   = open(CSV_FILE, "w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow([
    "timestamp_s", "tipo", "src_ip", "sport", "dst_ip", "dport",
    "cwnd", "ssthresh", "srtt_us", "snd_wnd", "rcv_wnd",
    "bytes_acked", "retrans", "estado"
])

start_ts  = None
retrans   = {}  # acumula retransmissoes por fluxo

# ── callback ────────────────────────────────────

def handle_event(cpu, data, size):
    global start_ts
    e = ct.cast(data, ct.POINTER(EventT)).contents

    if start_ts is None:
        start_ts = e.timestamp
    elapsed = (e.timestamp - start_ts) / 1e9
    flow    = fmt_flow(e)

    # retransmissao
    if e.oldstate == 254:
        retrans[flow] = retrans.get(flow, 0) + 1
        print(f"[{elapsed:8.3f}s] RETRANSMIT  {flow}  total={retrans[flow]}")
        csv_writer.writerow([f"{elapsed:.3f}", "RETRANSMIT",
                             ip4(e.src_ip), e.sport, ip4(e.dst_ip), e.dport,
                             "", "", "", "", "", "", retrans[flow], ""])

    # metrica tcp_probe
    elif e.oldstate == 255:
        print(f"[{elapsed:8.3f}s] METRIC      {flow:40s} "
              f"cwnd={e.cwnd:5d}  ssthresh={e.ssthresh:5d}  srtt={e.srtt:6d}us")
        csv_writer.writerow([f"{elapsed:.3f}", "METRIC",
                             ip4(e.src_ip), e.sport, ip4(e.dst_ip), e.dport,
                             e.cwnd, e.ssthresh, e.srtt,
                             e.snd_wnd, e.rcv_wnd, e.bytes_acked,
                             retrans.get(flow, 0), ""])

    # mudanca de estado
    else:
        old = TCP_STATES.get(e.oldstate, str(e.oldstate))
        new = TCP_STATES.get(e.newstate, str(e.newstate))
        print(f"[{elapsed:8.3f}s] STATE       {flow:40s} {old} -> {new}")
        csv_writer.writerow([f"{elapsed:.3f}", "STATE",
                             ip4(e.src_ip), e.sport, ip4(e.dst_ip), e.dport,
                             "", "", "", "", "", "", "", f"{old}->{new}"])

        # bonus: detecta congestionamento
        if flow in retrans and e.cwnd > 0:
            prev_cwnd = getattr(handle_event, "prev_cwnd", {}).get(flow, 0)
            if prev_cwnd > 0 and (prev_cwnd - e.cwnd) / prev_cwnd > 0.5:
                print(f"  *** CONGESTIONAMENTO {flow} cwnd {prev_cwnd}->{e.cwnd}")

    if not hasattr(handle_event, "prev_cwnd"):
        handle_event.prev_cwnd = {}
    handle_event.prev_cwnd[flow] = e.cwnd

    csv_file.flush()

# ── main ────────────────────────────────────────

b = BPF(text=BPF_PROGRAM)
b["events"].open_perf_buffer(handle_event)

print(f"TCP-CO rodando... gravando em '{CSV_FILE}' | Ctrl+C para parar")
print("-" * 90)

try:
    while True:
        b.perf_buffer_poll()
except KeyboardInterrupt:
    print(f"\nFinalizado. Dados em '{CSV_FILE}'")
finally:
    csv_file.close()