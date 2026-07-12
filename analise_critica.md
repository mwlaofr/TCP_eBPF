# Analise critica (parte 6)

## Questoes
### 1. Como a cwnd evolui durante o Slow Start?
Cresce exponencialmente, dobrando a cada RTT, ou seja, a cada ACK recebido, cwnd += 1, o que na prática duplica a janela por RTT.

### 2. Quando ocorre a transição para Congestion Avoidance? Como foi identificada?
Ocorre quando cwnd ≥ ssthresh, ou após a primeira perda. A partir daí o crescimento vira linear, isto e, +1 por RTT.

### 3. Impacto da perda sobre cwnd, ssthresh e throughput?
Na perda, o ssthresh cai à metade no Reno e cerca de 0.7 no Cubic, e o cwnd é rebaixado junto. Como o throughput é proporcional à cwnd, essa queda derruba a vazão e, como a recuperação é linear, o throughput médio fica bem abaixo do que a rede permitiria. Com perdas frequentes, uma nova perda chega antes da cwnd se recuperar da anterior, então o teto vai caindo a cada ciclo.

### 4. Qual algoritmo teve melhor desempenho? Justifique.
Com base na comparação, o Cubic tende a superar o Reno em vazão, porque reduz menos na perda (fator 0,7 vs 0,5 do Reno) e recupera mais rápido. Um exemplo disso e que em uma execucao do Experimento 4, o Cubic transferiu 276.101.351 bytes contra os 197.243.576 do Reno, cerca de 40% a mais de dados.

### 5. O RTT influenciou o desempenho? Como?
Sim. Como a cwnd só cresce uma vez por RTT, RTT alto retarda cada passo. Por exemplo, no Experimento 3 de 100ms, cada incremento levava ~200ms (100 de ida e 100 de volta), e o slow start demorou segundos.

RTT maior → crescimento mais lento → recuperação mais lenta → menor throughput

### 6. Limitações do eBPF para observabilidade TCP?
A programação do coletor depende de funções internas do kernel, como tcp_rcv_established e os campos da tcp_sock, que podem mudar entre versões. Já no seu funcionamento, o coletor eBPF captura todas as conexões, exigindo filtragem posterior para conexões específicas. Além disso, as amostras são por ACK, não por evento, o que gera linhas repetidas.

### 7. Vantagens do eBPF sobre modificar o kernel?
Não precisa recompilar nem reiniciar o kernel, já que roda com segurança (o verificador rejeita código perigoso), funcionando em kernels diferentes sem alterar o código-fonte do kernel.

### 8. Aplicações práticas em ambientes reais?
Monitoramento e diagnóstico de latência/perda em produção, detecção de gargalos TCP e ajuste de algoritmos de congestionamento por tipo de tráfego.