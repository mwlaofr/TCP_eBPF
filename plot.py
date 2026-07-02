#!/usr/bin/env python3
"""plot.py - gera os graficos da Parte 5 a partir dos CSVs do TCP-CO.
Uso:  python3 plot.py [--max N] arquivo.csv [outro.csv ...]
  --max N : teto de pontos por curva (padrao 200); reduz mostrando N espacados.
Instale o matplotlib com: sudo apt install -y python3-matplotlib
"""
import sys, csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MAX_POINTS = 200   # teto padrao de pontos por curva

def load(path):
    cwnd, srtt, retr = [], [], []
    last = None
    with open(path) as f:
        for row in csv.DictReader(f):
            c = int(row["cwnd"])
            if c == last:                 # descarta linhas repetidas (mesmo cwnd)
                continue
            last = c
            cwnd.append(c)
            srtt.append(int(row["srtt_us"]) / 1000.0)   # us -> ms
            retr.append(int(row["retrans"]))
    return cwnd, srtt, retr

def cap(seq, n):
    """Reduz 'seq' para no maximo n pontos igualmente espacados."""
    if len(seq) <= n:
        return list(seq)
    step = len(seq) / n
    return [seq[int(i * step)] for i in range(n)]

def main(paths, maxpts):
    fig, ax = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    for p in paths:
        cwnd, srtt, retr = load(p)
        cwnd, srtt, retr = cap(cwnd, maxpts), cap(srtt, maxpts), cap(retr, maxpts)
        x = range(len(cwnd))
        label = os.path.basename(p).replace(".csv", "")
        ax[0].plot(x, cwnd, marker="o", markersize=3, label=label)
        ax[1].plot(x, srtt, marker="o", markersize=3, label=label)
        ax[2].plot(x, retr, marker="o", markersize=3, label=label)
    ax[0].set_ylabel("cwnd (segmentos)"); ax[0].set_title("Janela de congestionamento x Amostra")
    ax[1].set_ylabel("RTT (ms)");          ax[1].set_title("RTT x Amostra")
    ax[2].set_ylabel("Retransmissoes");    ax[2].set_title("Retransmissoes acumuladas x Amostra")
    ax[2].set_xlabel(f"Amostra (mudancas de cwnd, max {maxpts} pontos)")
    for a in ax: a.grid(True, alpha=0.3); a.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig("graficos.png", dpi=120)
    print("Salvo: graficos.png")

if __name__ == "__main__":
    args = sys.argv[1:]
    maxpts = MAX_POINTS
    if "--max" in args:                    # opcional: --max N
        i = args.index("--max")
        maxpts = int(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(__doc__); sys.exit(1)
    main(args, maxpts)