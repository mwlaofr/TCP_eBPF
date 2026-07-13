#!/usr/bin/env python3
"""Graficos da Parte 5 a partir dos CSVs do TCP-CO
  python3 plot.py
  python3 plot.py --port N # troca a porta filtrada (padrao 5201)
  python3 plot.py --max N # usa apenas as primeiras N linhas (padrao: todas)
"""
import sys, csv, os, glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IN_DIR = "resultados"
OUT_DIR = "graficos"
PORT = "5201" # porta de destino do iperf3
MAX_POINTS = 100000 # por padrao plota todas 100000 linhas
INF = 2147483647 # ssthresh "infinito" (antes da primeira perda)

def load(path, port):
    cwnd, ssth, srtt, retr = [], [], [], []
    # t_vals = []
    last = None
    with open(path) as f:
        for row in csv.DictReader(f):
            if port is not None and row["dst_port"] != port:
                continue

            c = int(row["cwnd"])
            if c == last:  # so guarda quando o cwnd muda
                continue
            last = c

            s = int(row["ssthresh"])
            cwnd.append(c)
            ssth.append(None if s == INF else s)  # infinito nao entra na escala
            srtt.append(int(row["srtt_us"]) / 1000.0)
            retr.append(int(row["retrans"]))
            # t_vals.append(float(row["t"])) 
    # return cwnd, ssth, srtt, retr, t_vals
    return cwnd, ssth, srtt, retr

def plotar(label, cwnd, ssth, srtt, retr, maxpts, saida): # colocar t_vals caso queira por tempo
    # mantem apenas as primeiras n linhas consecutivas
    cwnd = cwnd[:maxpts]
    ssth = ssth[:maxpts]
    srtt = srtt[:maxpts]
    retr = retr[:maxpts]
    # t_vals = t_vals[:maxpts]

    x = range(len(cwnd))
    # x = t_vals
    fig, ax = plt.subplots(3, 1, figsize=(11, 12), sharex=True)
    ax[0].plot(x, cwnd, marker="o", markersize=3, label="cwnd")
    ax[0].plot(x, ssth, marker="", linestyle="--", label="ssthresh")  # linha tracejada
    ax[0].set_ylabel("segmentos"); ax[0].set_title("cwnd e ssthresh x Amostra")
    # ax[0].set_ylabel("segmentos"); ax[0].set_title("cwnd e ssthresh x Tempo")
    ax[1].plot(x, srtt, marker="o", markersize=3)
    ax[1].set_ylabel("RTT (ms)"); ax[1].set_title("RTT x Amostra")
    # ax[1].set_ylabel("RTT (ms)"); ax[1].set_title("RTT x Tempo")
    ax[2].plot(x, retr, marker="o", markersize=3)
    ax[2].set_ylabel("Retransmissoes"); ax[2].set_title("Retransmissoes acumuladas x Amostra")
    # ax[2].set_ylabel("Retransmissoes"); ax[2].set_title("Retransmissoes acumuladas x Tempo")
    ax[2].set_xlabel(f"Amostra (mudancas de cwnd, ate {maxpts} primeiras)")
    # ax[2].set_xlabel(f"Tempo (s), ate {maxpts} primeiras amostras")
    ax[0].legend(fontsize=8)

    for a in ax: 
        a.grid(True, alpha=0.3)
    
    fig.suptitle(label, fontsize=11)
    fig.tight_layout()
    fig.savefig(saida, dpi=120)
    plt.close(fig)

    print("Salvo:", saida)

def main(port, maxpts):
    csvs = sorted(glob.glob(os.path.join(IN_DIR, "*.csv")))

    if not csvs:
        print(f"Nenhum CSV em ./{IN_DIR}/  (rode os experimentos primeiro)")
        return
    
    # cria a pasta se necessario
    os.makedirs(OUT_DIR, exist_ok=True)

    for p in csvs:
        cwnd, ssth, srtt, retr = load(p, port)
        # cwnd, ssth, srtt, retr, t_vals = load(p, port)
        label = os.path.basename(p).replace(".csv", "")

        if not cwnd:
            print(f"  (aviso: {label} sem dados para a porta {port})")
            continue

        # passar t_vals caso queira por tempo
        plotar(label, cwnd, ssth, srtt, retr, maxpts, os.path.join(OUT_DIR, label + ".png"))

args = sys.argv[1:]
port = PORT 
maxpts = MAX_POINTS

if "--max" in args:
    i = args.index("--max")
    maxpts = int(args[i + 1])
    del args[i:i + 2]

if "--port" in args:
    i = args.index("--port")
    port = args[i + 1]
    del args[i:i + 2]

main(port, maxpts)