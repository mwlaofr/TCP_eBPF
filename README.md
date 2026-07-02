# TCP Congestion Observatory (TCP-CO)

Ferramenta em eBPF que monitora conexoes TCP e coleta metricas de controle de
congestionamento (janela cwnd, ssthresh, RTT, retransmissoes, estado do algoritmo)
lendo a `tcp_sock` do kernel. Exporta os dados em CSV e gera graficos.

## Arquivos

| Arquivo | O que e |
|---|---|
| `tcpco.bpf.c` | Programa que roda **dentro do kernel** (coleta as metricas). |
| `tcpco.c` | Programa de usuario que carrega o eBPF e grava o CSV. |
| `Makefile` | Compila os dois acima e gera o executavel `tcpco`. |
| `run_experimentos.sh` | Roda os 4 experimentos automaticamente. |
| `plot.py` | Gera os graficos a partir dos CSVs. |

## 1. Instalar as dependencias (uma vez so)

```bash
sudo apt update
sudo apt install -y clang llvm libbpf-dev libelf-dev bpftool \
     linux-tools-$(uname -r) linux-headers-$(uname -r) \
     iperf3 iproute2 python3-matplotlib
```

Confirme que o kernel tem BTF (o arquivo precisa existir):
```bash
ls /sys/kernel/btf/vmlinux
```

Se o comando `bpftool` nao for encontrado, adicione ao PATH:
```bash
export PATH=$PATH:/usr/lib/linux-tools/$(uname -r)
```

## 2. Compilar

```bash
make
```
Isso gera o executavel `tcpco`.

## 3. Rodar

### Opcao A — todos os experimentos de uma vez (recomendado)

```bash
sudo ./run_experimentos.sh lo 127.0.0.1
```
Espere terminar (aparece `== Fim ==`). Os CSVs ficam na pasta `resultados/`.
Para uma rodada mais rapida durante testes, reduza a duracao:
```bash
sudo DUR=15 ./run_experimentos.sh lo 127.0.0.1
```

### Opcao B — rodar so o coletor manualmente

Terminal 1 (coletor):
```bash
sudo ./tcpco saida.csv        # Ctrl-C para parar
```
Terminal 2 (gera trafego):
```bash
iperf3 -s
iperf3 -c 127.0.0.1 -t 30
```

## 4. Gerar os graficos

```bash
python3 plot.py resultados/exp1_cwnd_cubic.csv
```
Isso cria `graficos.png`. Para comparar dois algoritmos no mesmo grafico:
```bash
python3 plot.py resultados/exp4_cmp_cubic.csv resultados/exp4_cmp_bbr.csv
```
Para reduzir o numero de pontos (grafico mais limpo):
```bash
python3 plot.py --max 100 resultados/exp2_perda_cubic.csv
```

## Emular condicoes de rede (manual)

O `run_experimentos.sh` ja faz isso, mas para testar na mao:
```bash
sudo tc qdisc add dev lo root netem loss 1%       # 1% de perda
sudo tc qdisc add dev lo root netem delay 100ms   # RTT de 100ms
sudo tc qdisc del dev lo root                       # limpar
```

Trocar o algoritmo de congestionamento:
```bash
sudo sysctl -w net.ipv4.tcp_congestion_control=cubic   # ou reno, bbr
```

## Observacoes

- Todos os comandos de coleta precisam de `sudo` (carregam eBPF no kernel).
- Use `lo` para testes em `127.0.0.1`; para duas maquinas reais, use a
  interface fisica (veja com `ip a`).
- No loopback o cwnd cresce muito rapido; os experimentos com `tc netem`
  (perda/RTT) mostram melhor a dinamica de congestionamento.