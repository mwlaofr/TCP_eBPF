# Makefile - TCP Congestion Observatory
CLANG   ?= clang
BPFTOOL ?= bpftool
ARCH    := $(shell uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')

CFLAGS  := -g -O2 -Wall -I.
BPF_CFLAGS := -g -O2 -target bpf -D__TARGET_ARCH_$(ARCH) -I.

.PHONY: all clean

all: tcpco

# 1) Gera o vmlinux.h a partir do BTF do kernel em execução (precisa CONFIG_DEBUG_INFO_BTF).
vmlinux.h:
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h

# 2) Compila o objeto BPF.
tcpco.bpf.o: tcpco.bpf.c vmlinux.h
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

# 3) Gera o skeleton .h a partir do objeto BPF.
tcpco.skel.h: tcpco.bpf.o
	$(BPFTOOL) gen skeleton $< > $@

# 4) Compila o loader user-space linkando com libbpf.
tcpco: tcpco.c tcpco.skel.h
	$(CLANG) $(CFLAGS) $< -lbpf -lelf -lz -o $@

clean:
	rm -f tcpco tcpco.bpf.o tcpco.skel.h vmlinux.h tcpco.csv