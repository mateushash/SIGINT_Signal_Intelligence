# Manual do SIGINT (Criasdecrip)
---

## Estrutura do Projeto

O projeto está organizado para manter a raiz limpa:
- **`src/`**: Código fonte Python (Buffer, Worker, Score Service, etc).
- **`web/`**: Interface visual (Dashboard).
- **`data/`**: Banco de dados e listas de palavras.
- **`logs/`**: Arquivos de log gerados durante a execução.

---

## 1. Como INICIAR tudo (Ligar o sistema)

Para iniciar o RabbitMQ no Docker e todos os serviços Python de uma só vez, abra o terminal na raiz do projeto e rode:

```bash
# Permissões (só precisa rodar uma vez)
chmod +x *.sh

# Iniciar o sistema
./start.sh
```

> [!IMPORTANT]
> **Certifique-se de que o Docker Desktop está aberto no seu Mac!**

---

## 2. Como PARAR tudo (Desligar o sistema)

No terminal, na raiz do projeto, rode:

```bash
./stop.sh
```

---

## 3. Como rodar MANUALMENTE (Modo 4 Terminais)

Se você quiser ver os logs acontecendo em tempo real:

1. Pare tudo: `./stop.sh`
2. **Garanta o RabbitMQ ligado:** 
   `docker start rabbitmq || docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management`
3. Abra **4 janelas** de terminal na raiz do projeto.
4. **No Terminal 1:** `python3 src/buffer.py`
5. **No Terminal 2:** `python3 src/worker_rabbit.py`
6. **No Terminal 3:** `python3 src/score_service.py`
7. **No Terminal 4:** `python3 sending_test.py`

---

## 3.1 Rodar só o worker em outra máquina via Tailscale

Na máquina remota, aponte o worker para o IP Tailscale da máquina que roda o RabbitMQ e o Buffer:

```bash
export SIGINT_RABBITMQ_HOST=100.107.140.27
export SIGINT_BUFFER_URL=http://100.107.140.27:5050/retorno
./start_worker.sh
```

Se preferir, rode direto:

```bash
SIGINT_RABBITMQ_HOST=100.107.140.27 SIGINT_BUFFER_URL=http://100.107.140.27:5050/retorno python3 src/worker_rabbit.py
```

---

## 4. Como ver os resultados e testar

**1. Enviar uma mensagem de teste:**
```bash
python3 sending_test.py
```

**2. Ver o Dashboard:**
Abra o arquivo `web/painel.html` no Chrome. Se a API estiver em outra máquina da Tailscale, passe o host na URL:
`web/painel.html?host=100.107.140.27`

**3. Ver na Central via Terminal:**
```bash
python3 src/central.py
```

---

## 5. Endpoints da API REST

Todos os endpoints rodam em `http://<host>:5050` (por padrão, o host Tailscale configurado no dashboard).

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/health` | Status do sistema e RabbitMQ |
| `GET` | `/api/status` | Monitor de pacotes ao vivo |
| `GET` | `/api/stats` | Estatísticas gerais |
| `GET` | `/api/scores` | Últimos scores calculados |
| `GET` | `/api/mensagens` | Histórico de mensagens |
| `GET` | `/api/validar/<id>` | Validação inteligente de texto |
