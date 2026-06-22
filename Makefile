IFACE    ?= lo
DURATION ?= 10

.PHONY: install exp1 exp2 exp3 exp4_cubic exp4_bbr graphs clean help

install:
	sudo apt install -y python3-bpfcc bpfcc-tools iperf3 iproute2 python3-matplotlib python3-pandas

exp1:
	mkdir -p results
	sudo sysctl -w net.ipv4.tcp_congestion_control=cubic
	iperf3 -s -1 &
	sleep 1
	sudo python3 tcp_co.py &
	iperf3 -c 127.0.0.1 -t $(DURATION)
	sudo pkill -f tcp_co.py
	cp tcp_metrics.csv results/exp1_cubic.csv
	@echo ">>> Salvo em results/exp1_cubic.csv"

exp2:
	mkdir -p results
	sudo sysctl -w net.ipv4.tcp_congestion_control=cubic
	sudo tc qdisc add dev $(IFACE) root netem loss 1%
	iperf3 -s -1 &
	sleep 1
	sudo python3 tcp_co.py &
	iperf3 -c 127.0.0.1 -t $(DURATION)
	sudo pkill -f tcp_co.py
	sudo tc qdisc del dev $(IFACE) root
	cp tcp_metrics.csv results/exp2_loss.csv
	@echo ">>> Salvo em results/exp2_loss.csv"

exp3:
	mkdir -p results
	sudo sysctl -w net.ipv4.tcp_congestion_control=cubic
	sudo tc qdisc add dev $(IFACE) root netem delay 100ms
	iperf3 -s -1 &
	sleep 1
	sudo python3 tcp_co.py &
	iperf3 -c 127.0.0.1 -t $(DURATION)
	sudo pkill -f tcp_co.py
	sudo tc qdisc del dev $(IFACE) root
	cp tcp_metrics.csv results/exp3_100ms.csv
	@echo ">>> Salvo em results/exp3_100ms.csv"

exp4_cubic:
	mkdir -p results
	sudo sysctl -w net.ipv4.tcp_congestion_control=cubic
	iperf3 -s -1 &
	sleep 1
	sudo python3 tcp_co.py &
	iperf3 -c 127.0.0.1 -t $(DURATION)
	sudo pkill -f tcp_co.py
	cp tcp_metrics.csv results/exp4_cubic.csv
	@echo ">>> Salvo em results/exp4_cubic.csv"

exp4_bbr:
	mkdir -p results
	sudo sysctl -w net.ipv4.tcp_congestion_control=bbr
	iperf3 -s -1 &
	sleep 1
	sudo python3 tcp_co.py &
	iperf3 -c 127.0.0.1 -t $(DURATION)
	sudo pkill -f tcp_co.py
	sudo sysctl -w net.ipv4.tcp_congestion_control=cubic
	cp tcp_metrics.csv results/exp4_bbr.csv
	@echo ">>> Salvo em results/exp4_bbr.csv"

graphs:
	python3 graphs.py

clean:
	rm -f tcp_metrics.csv
	rm -rf results

help:
	@echo "make exp1         slow start sem netem"
	@echo "make exp2         1% perda de pacotes"
	@echo "make exp3         RTT 100ms"
	@echo "make exp4_cubic   algoritmo cubic"
	@echo "make exp4_bbr     algoritmo bbr"
	@echo "make graphs       gera graficos"
	@echo "make clean        limpa arquivos"