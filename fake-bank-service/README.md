# 🏦 Fake Bank Service — PIX Simulator

Serviço responsável por **simular o comportamento de um banco/PSP**, processando pagamentos via PIX e disparando **webhooks assinados** para sistemas integrados.

Este serviço representa o **lado externo** da integração, permitindo testar fluxos reais de pagamento **assíncronos e idempotentes**.

---

## 🎯 Responsabilidade do serviço

* Registrar cobranças recebidas do sistema principal
* Processar pagamentos PIX de forma simulada
* Disparar **webhooks assinados (HMAC)** para sistemas clientes
* Implementar **retry com exponential backoff**
* Propagar **X-Request-Id** para observabilidade cross-service
* Simular falhas e comportamento real de provedores de pagamento

---

## 🧠 Conceitos aplicados

* Webhooks assinados (HMAC + SHA-256)
* Retry automático com exponential backoff
* Idempotência por `event_id`
* Observabilidade cross-service
* Separação clara por rotas, serviços e clientes
* Simulação de integração bancária realista

---

## 🛠️ Tecnologias

* Python 3.12
* Flask
* Requests
* Docker

---

## 📂 Estrutura do Serviço

```text
fake-bank-service/
├── app.py
├── routes/
│   └── pix.py
├── services/
│   └── webhook_dispatcher.py
├── clients/
│   └── webhook_client.py
├── security/
│   └── hmac.py
├── config.py
└── requirements.txt
```

---

## 📦 Variáveis de Ambiente

Arquivo `.env` ou `config.py`:

```env
WEBHOOK_SECRET=super-secret-webhook-key
```

> A `WEBHOOK_SECRET` deve ser a mesma configurada no `payment-charges-api`.

---

## ▶️ Como rodar isoladamente

### Sem Docker

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Serviço disponível em:

```
http://localhost:6000
```

---

### Com Docker

Execute a partir da **raiz do projeto**:

```bash
docker compose up fake-bank-service
```

---

## 🔗 Endpoints

### Registrar cobrança

```
POST /bank/pix/charges
```

Payload:

```json
{
  "external_id": "uuid",
  "value": 100.0,
  "webhook_url": "http://payment-charges-api:5000/webhooks/pix"
}
```

Resposta:

```json
{
  "message": "Charge registered in bank"
}
```

---

### Processar pagamento PIX

```
POST /bank/pix/pay
```

Payload:

```json
{
  "external_id": "uuid"
}
```

> Este endpoint **simula o processamento bancário** e dispara o webhook automaticamente.

Resposta:

```json
{
  "message": "PIX processed by bank",
  "event_id": "evt_xxx"
}
```

---

## 🔔 Webhook disparado

### Headers enviados

```
X-Signature: sha256=...
X-Timestamp: <unix-seconds>
X-Event-Id: evt_xxx
X-Request-Id: demo-001
```

### Body

```json
{
  "event_id": "evt_xxx",
  "external_id": "uuid",
  "value": 100.0,
  "status": "PAID"
}
```

---

## 🔁 Retry + Backoff

* Webhooks são reenviados automaticamente em caso de falha
* Estratégia utilizada:

  * Exponential backoff
  * Jitter para evitar thundering herd
  * Número máximo de tentativas configurável

> Simula o comportamento de bancos e gateways reais.

---

## 🔐 Segurança

* Assinatura HMAC baseada no **raw body**
* Timestamp para proteção contra replay
* Idempotência por `event_id`
* Headers obrigatórios validados no sistema receptor

---

## 📌 Observação importante

Este serviço **não persiste estado bancário** (intencionalmente).
Seu foco é simular **integração externa realista**, não substituir um banco real.

---

## 🧪 Status do projeto

* Retry/backoff: ✅ implementado
* Assinatura HMAC: ✅ implementada
* Integração com Payment API: ✅ completa
* Persistência bancária: ❌ intencionalmente ausente

---

### 🏁 Conclusão

O Fake Bank Service permite testar fluxos de pagamento PIX **como ocorrem em produção**, sendo uma peça essencial para validar segurança, idempotência e comportamento assíncrono da plataforma.

---

