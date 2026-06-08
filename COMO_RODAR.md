# Manual do SIGINT (Criasdecrip)
---

O sistema possui uma arquitetura com **Alta Disponibilidade Simples (Failover via Scripting)**. Ele roda 3 Buffers simultâneos e o tráfego é redirecionado automaticamente se algum deles cair, sem precisar de Docker Compose ou arquiteturas complexas.

## Estrutura do Projeto

- **`src/`**: Código fonte Python (Buffer, Worker, Score Service, etc).
- **`web/`**: Interface visual (Dashboard).
- **`data/`**: Banco de dados e listas de palavras.
- **`logs/`**: Arquivos de log gerados durante a execução.

---

## 1. Como INICIAR tudo (Ligar o sistema)

Para iniciar o RabbitMQ no Docker e todos os serviços Python de uma só vez (incluindo os 3 buffers de failover), abra o terminal na raiz do projeto e rode:

```bash
# Permissões (só precisa rodar uma vez)
chmod +x *.sh

# Iniciar o sistema
./start.sh
```

> [!IMPORTANT]
> **Certifique-se de que o Docker Desktop está aberto no seu Mac!** Ele será usado apenas para o RabbitMQ.

---

##  2. Como PARAR tudo (Desligar o sistema)

No terminal, na raiz do projeto, rode:

```bash
./stop.sh
```

---

## 🖥️ 3. Como ver os resultados e testar

**1. Ver o Dashboard:**
Abra o arquivo `web/painel.html` com dois cliques (no navegador).
Lá em cima, você verá 3 indicadores mostrando quais Buffers estão online: `B1(5050)`, `B2(5051)`, `B3(5052)`.

**2. Enviar uma mensagem de teste:**
```bash
python3 sending_test.py
```

---

##  4. Como testar o FAILOVER (Derrubar ou Ligar um Buffer)

Para ver a Alta Disponibilidade funcionando, você pode derrubar um buffer propositalmente:

1. Deixe o sistema rodando.
2. Rode um dos comandos abaixo para matar o buffer desejado:
   ```bash
   ./kill_buffer.sh 1   # Mata o B1 (Porta 5050)
   ./kill_buffer.sh 2   # Mata o B2 (Porta 5051)
   ./kill_buffer.sh 3   # Mata o B3 (Porta 5052)
   ```
3. Olhe no `painel.html`. A bolinha do buffer morto vai ficar vermelha instantaneamente.
4. Rode `python3 sending_test.py`. A mensagem será enviada perfeitamente pelos buffers que sobraram de forma invisível via Load Balancer.

**Para ligar o buffer de volta:**
   ```bash
   ./start_buffer.sh 1  # Liga o B1 de volta
   ./start_buffer.sh 2  # Liga o B2 de volta
   ./start_buffer.sh 3  # Liga o B3 de volta
   ```

---

##  5. Endpoints da API REST

A API atende publicamente no **Load Balancer (porta 8080)**. O tráfego é roteado automaticamente para a 5050, 5051 ou 5052 nos bastidores.

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `http://localhost:8080/api/health` | Status do sistema e RabbitMQ |
| `GET` | `http://localhost:8080/api/status` | Monitor de pacotes ao vivo |
| `GET` | `http://localhost:8080/api/stats` | Estatísticas gerais |
| `GET` | `http://localhost:8080/api/scores` | Últimos scores calculados |
| `GET` | `http://localhost:8080/api/mensagens` | Histórico de mensagens |
| `GET` | `http://localhost:8080/api/validar/<id>` | Validação inteligente de texto |
