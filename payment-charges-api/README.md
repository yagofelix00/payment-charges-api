# 💳 Payment Charges API

API responsável por **criação de cobranças** e **confirmação de pagamentos via webhook PIX**.
Este serviço **não confirma pagamentos por chamada direta** — a confirmação ocorre **exclusivamente via webhook assinado**, simulando integração real com um banco/PSP.

---

## 🎯 Responsabilidade do serviço

* Criar cobranças (`PENDING`)
* Controlar expiração via **Redis TTL**
* Receber webhooks assinados do banco
* Validar segurança, idempotência e integridade
* Atualizar cobrança para `PAID` ou `EXPIRED`
* Expor consulta de status da cobrança

---

## 🧠 Conceitos aplicados

* Webhooks assinados (**HMAC SHA-256**)
* Proteção contra replay attack (**timestamp + tolerance window**)
* **Idempotência** por `event_id` (Redis)
* **Redis como fonte de verdade** para expiração
* Rate limiting em endpoints sensíveis
* Observabilidade com **X-Request-Id**
* Logs estruturados com auditoria

---

## 🛠️ Tecnologias

* Python 3.12
* Flask
* Flask SQLAlchemy
* SQLite (ambiente local)
* Redis
* Docker

---

## 📂 Estrutura do Serviço

```text
payment-charges-api/
├── app.py                    # Flask app factory / bootstrap
├── extensions.py             # Limiter, etc (extensões Flask)
├── requirements.txt
├── .env
│
├── routes/                   # Camada HTTP (controllers)
│   ├── charges.py            # POST /charges, GET /charges/{id}
│   └── webhooks.py           # POST /webhooks/pix
│
├── services/                 # Regras de negócio
│   └── charge_service.py     # Expiração, validações, helpers
│
├── db_models/                # Models SQLAlchemy (Charge, enums)
│   └── charges.py
│
├── repository/               # Banco / ORM setup
│   └── database.py           # db = SQLAlchemy()
│
├── security/                 # Segurança (camada transversal)
│   ├── auth.py               # API key (quando aplicável)
│   ├── idempotency.py        # Idempotência via Redis (event_id)
│   └── webhook_signature.py  # HMAC + timestamp validation
│
├── infrastructure/           # Integrações externas (Redis etc.)
│   └── redis_client.py
│
├── audit/                    # Observabilidade e auditoria
│   ├── logger.py             # Logger com request_id
│   └── request_context.py    # Init/get request_id (X-Request-Id)
│
├── instance/                 # SQLite (database.db) e arquivos locais
│   └── database.db
│
└── logs/                     # Logs persistidos (audit.log, etc.)
    └── audit.log
```

---

## 📦 Variáveis de Ambiente

Arquivo `.env`:

```env
FLASK_ENV=development
SECRET_KEY=your-secret-key

# Webhook
WEBHOOK_SECRET=super-secret-webhook-key

# Redis
REDIS_URL=redis://redis:6379/0
```

---

## ▶️ Como rodar isoladamente

### Sem Docker

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask run
```

A API ficará disponível em:

```
http://localhost:5000
```

---

### Com Docker (recomendado)

Execute a partir da **raiz do projeto**:

```bash
docker compose up payment-charges-api
```

---

## 🔗 Endpoints principais

### Criar cobrança

```
POST /charges
```

Payload:

```json
{
  "value": 100.0
}
```

Resposta:

```json
{
  "id": 1,
  "external_id": "uuid",
  "status": "PENDING"
}
```

---

### Consultar cobrança

```
GET /charges/{id}
```

Resposta:

```json
{
  "id": 1,
  "value": 100.0,
  "status": "PAID",
  "expires_at": "2026-01-24T12:34:56"
}
```

---

### Webhook PIX (recebido do banco)

```
POST /webhooks/pix
```

#### Headers obrigatórios

```
X-Signature: sha256=...
X-Timestamp: <unix-seconds>
X-Event-Id: evt_xxx
```

#### Body

```json
{
  "event_id": "evt_xxx",
  "external_id": "uuid",
  "value": 100.0,
  "status": "PAID"
}
```

---

## 🔐 Segurança do Webhook

* Assinatura HMAC baseada no **raw body**
* Validação de timestamp (tolerance window)
* Proteção contra eventos duplicados (idempotência)
* Webhooks inválidos são rejeitados com status **401 / 400**

> Inspirado em implementações reais de provedores como **Stripe** e **Mercado Pago**.

---

## 📜 Documentação OpenAPI

* Contrato oficial da API: `openapi.yaml`
* Define endpoints, schemas, headers e erros
* Pode ser usado para Swagger UI ou geração de clientes

---

## 🧪 Status do projeto

* Testes automatizados: ⏳ pendente
* Integração com Fake Bank: ✅ completa
* Fluxo de pagamento assíncrono: ✅ funcional

---

## 📌 Observação importante

Este serviço **não expõe endpoints para “confirmar pagamento manualmente”**.
A confirmação ocorre **somente via webhook**, simulando comportamento real de sistemas financeiros.

---


