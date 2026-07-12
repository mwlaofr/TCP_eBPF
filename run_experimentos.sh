#!/usr/bin/env bash
# run_experimentos.sh - orquestra os 4 experimentos do PDF (versao libbpf).
#
# Uso:  sudo ./run_experimentos.sh [iface] [ip_servidor]
#   ex.: sudo ./run_experimentos.sh lo 127.0.0.1
#
# Padrao IFACE=lo porque os testes usam 127.0.0.1 (loopback): o tc netem
# precisa ser aplicado em lo para afetar esse trafego.
set -euo pipefail

IFACE="${1:-lo}"
SERVER="${2:-127.0.0.1}"
DUR="${DUR:-30}"
OUT="resultados"; mkdir -p "$OUT"

need() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Erro: comando '$1' não encontrado."
        exit 1
    }
}

need iperf3
need tc
need sysctl

if [[ ! -x ./tcpco ]]; then
    echo "Erro: executável ./tcpco não encontrado."
    echo "Execute: make"
    exit 1
fi

limpa() { 
  tc qdisc del dev "$IFACE" root 2>/dev/null || true
}

cc() { 
  sysctl -w net.ipv4.tcp_congestion_control="$1" >/dev/null
  echo "  CC=$1"
}

coleta() { 
  local nome="$1" # nome
  local alg="$2" # algoritmo
  local csv="$OUT/${nome}_${alg}.csv"
  local pid
  cc "$alg"
  echo "  -> $csv"
  iperf3 -s -1 >/dev/null 2>&1 & # servidor fecha apos 1 conexao
  sleep 1
  ./tcpco "$csv" &
  pid=$!
  sleep 1
  iperf3 -c "$SERVER" -t "$DUR" >/dev/null 2>&1 || echo "     (iperf3 falhou)"
  sleep 1
  kill "$pid" 2>/dev/null || true  # encerra o coletor
  pkill -f iperf3 2>/dev/null || true  # mata servidor e clientes pendentes
  wait "$pid" 2>/dev/null || true
  sleep 1 # deixa as conexoes fecharem antes do proximo
}


echo "[Exp 1] Crescimento da cwnd (rede limpa)"
limpa
coleta exp1_cwnd cubic

echo "[Exp 2] Perdas aleatorias (1%)"
limpa
tc qdisc add dev "$IFACE" root netem loss 1%
coleta exp2_perda cubic
limpa

echo "[Exp 3] RTT elevado (100/200/500 ms)"
for rtt in 100 200 500
do
  limpa
  tc qdisc add dev "$IFACE" root netem delay "${rtt}ms"
  coleta "exp3_rtt${rtt}" cubic
done
limpa

echo "[Exp 4] Comparacao entre 2 algoritmos (cubic x reno)"
limpa
tc qdisc add dev "$IFACE" root netem delay 50ms loss 0.5%
for alg in cubic reno
do 
  coleta exp4_cmp "$alg"
done
limpa
cc cubic

echo "== Fim. CSVs em ./$OUT/ =="
echo "Graficos: python3 plot.py   (le ./$OUT/ e gera ./graficos/)"