import difflib
from common import *

README = '''# payments-api

The service behind the checkout page's **Pay** button.

- `POST /api/orders/{order_id}/pay` with `{"card_token": ...}` charges the card
  through the card payment provider's REST API and marks the order paid.
- `GET /api/orders/{order_id}` returns an order (also used by the order page).
- Four instances (api-1 to api-4) run behind one load balancer
  (`deploy/load-balancer.yaml`). Each runs uvicorn with one worker process.
- PostgreSQL 17 holds `orders` and `payments`.

Python 3.12, FastAPI 0.118, SQLAlchemy 2.0, httpx 0.28.
'''

REQS = '''fastapi==0.118.0
uvicorn==0.37.0
sqlalchemy==2.0.43
psycopg[binary]==3.2.10
httpx==0.28.1
pydantic-settings==2.11.0
'''

CONFIG = '''from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    provider_url: str
    provider_key: str


settings = Settings()
'''

MAIN = '''import logging
import time

from fastapi import FastAPI, Request

from app import orders, payments

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("http")

app = FastAPI()
app.include_router(payments.router)
app.include_router(orders.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    log.info("request done %s %s %s %.3fs", request.method, request.url.path,
             response.status_code, time.monotonic() - started)
    return response
'''

DB = '''from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=0,
    pool_timeout=30,
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session():
    """One session and one transaction per request. Commits when the request
    handler returns; rolls back if it raises."""
    with SessionLocal() as session:
        with session.begin():
            yield session
'''

MODELS = '''from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | paid | cancelled
    total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    payment_id: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    charge_id: Mapped[str] = mapped_column(String(64))
    amount_cents: Mapped[int] = mapped_column(Integer)
    # now() in PostgreSQL is the start time of the current transaction
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
'''

PROVIDER = '''import httpx

from app.config import settings

client = httpx.Client(
    base_url=settings.provider_url,
    timeout=httpx.Timeout(30.0, connect=5.0),
    headers={"Authorization": f"Bearer {settings.provider_key}"},
)


class ProviderError(Exception):
    pass


def create_charge(amount_cents: int, currency: str, card_token: str, description: str,
                  idempotency_key: str | None = None) -> dict:
    """POST /v1/charges. The provider keeps idempotency keys for 24 hours: a request
    repeating a key gets the first request's result instead of a new charge."""
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    resp = client.post(
        "/v1/charges",
        json={"amount": amount_cents, "currency": currency, "source": card_token,
              "description": description},
        headers=headers,
    )
    if resp.status_code >= 400:
        raise ProviderError(f"{resp.status_code}: {resp.text[:200]}")
    return resp.json()
'''

PAYMENTS = '''import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import provider
from app.db import get_session
from app.models import Order, Payment

router = APIRouter()
log = logging.getLogger("payments")


class PayRequest(BaseModel):
    card_token: str


@router.post("/api/orders/{order_id}/pay")
def pay(order_id: int, body: PayRequest, session: Session = Depends(get_session)):
    t0 = time.monotonic()
    session.connection()  # takes a connection from the pool and begins the transaction
    log.info("db connection order=%s wait=%.2fs", order_id, time.monotonic() - t0)

    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "order not found")
    log.info("pay order=%s status_read=%s", order.id, order.status)
    if order.status == "paid":
        return {"status": "paid", "payment_id": order.payment_id}

    started = time.monotonic()
    log.info("provider POST /v1/charges order=%s amount=%s", order.id, order.total_cents)
    charge = provider.create_charge(
        amount_cents=order.total_cents,
        currency=order.currency,
        card_token=body.card_token,
        description=f"order {order.id}",
    )
    log.info("provider %s charge=%s %.3fs", charge["status"], charge["id"], time.monotonic() - started)

    order.status = "paid"
    order.payment_id = charge["id"]
    session.add(Payment(order_id=order.id, charge_id=charge["id"], amount_cents=order.total_cents))
    return {"status": "paid", "payment_id": charge["id"]}
'''

ORDERS = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Order

router = APIRouter()


@router.get("/api/orders/{order_id}")
def get_order(order_id: int, session: Session = Depends(get_session)):
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "order not found")
    return {"id": order.id, "status": order.status, "total_cents": order.total_cents,
            "currency": order.currency, "payment_id": order.payment_id}
'''

CHECKOUT = '''// Called when the customer presses "Pay" on the checkout page.
export async function payOrder(orderId, cardToken) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    const res = await fetch(`/api/orders/${orderId}/pay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card_token: cardToken }),
    });
    if (res.ok) return res.json();
    if (res.status < 500) throw new Error(await res.text());
    // 5xx: the server had a problem, try again
  }
  throw new Error("Payment failed, please try again");
}
'''

LB = '''# Load balancer in front of the API instances
listeners:
  - port: 443
    protocol: HTTPS
    default_action: forward:api

target_groups:
  api:
    targets: [api-1:8000, api-2:8000, api-3:8000, api-4:8000]
    algorithm: round_robin
    health_check:
      path: /healthz
      interval_seconds: 10

# Time to wait for the upstream to send a response before answering 504.
idle_timeout_seconds: 10
'''

files = {
    "README.md": README, "requirements.txt": REQS, "app/config.py": CONFIG, "app/main.py": MAIN,
    "app/db.py": DB, "app/models.py": MODELS, "app/provider.py": PROVIDER, "app/payments.py": PAYMENTS,
    "app/orders.py": ORDERS, "web/checkout.js": CHECKOUT, "deploy/load-balancer.yaml": LB,
}

# ---- one order's timeline, derived once ----------------------------------
def t(s):  # seconds after 14:22:00 -> "14:22:SS.mmm"
    return f"14:22:{s:06.3f}"

A_in, A_wait = 3.118, 0.00
A_read = A_in + 0.006
A_prov = A_in + 0.013
A_took = 11.771
A_ok = A_prov + A_took
A_done = A_ok + 0.008
LB_TIMEOUT = 10.0
B_in = A_in + LB_TIMEOUT + 0.001 + 0.045  # browser retries right after the 504
B_wait = 0.62
B_conn = B_in + 0.002 + B_wait
B_read = B_conn + 0.005
B_prov = B_read + 0.010
B_took = 11.211
B_ok = B_prov + B_took
B_done = B_ok + 0.008
C_in = B_in + LB_TIMEOUT + 0.000 + 0.045
C_wait = 7.38
C_conn = C_in + 0.001 + C_wait
C_read = C_conn + 0.006
C_done = C_read + 0.025
assert A_ok > B_read, "B must read before A finishes"
assert C_read > B_done, "C reads after both commits"
assert round(C_done - C_in, 3) == 7.412
assert A_ok - A_in > LB_TIMEOUT and B_ok - B_in > LB_TIMEOUT

orders_paid, twice, thrice = 6339, 37, 4
total_orders = orders_paid + twice + thrice
assert total_orders == 6380

LOGS = f'''Logs for order 88213, yesterday afternoon. All sources use the same clock (UTC).

== Load balancer access log: POST /api/orders/88213/pay ==
received       client      upstream  status  upstream_time  note
{t(A_in)}   browser-7f  api-2     504     10.001 s       no response from upstream within idle timeout (10 s)
{t(B_in)}   browser-7f  api-4     504     10.000 s       no response from upstream within idle timeout (10 s)
{t(C_in)}   browser-7f  api-1     200      7.412 s

== API application log, api-1, api-2 and api-4, merged by time (the log shipper adds the instance name) ==
{t(A_in + 0.001)} api-2 INFO db connection order=88213 wait=0.00s
{t(A_read)} api-2 INFO pay order=88213 status_read=pending
{t(A_prov)} api-2 INFO provider POST /v1/charges order=88213 amount=4999
{t(B_conn)} api-4 INFO db connection order=88213 wait={B_wait:.2f}s
{t(B_read)} api-4 INFO pay order=88213 status_read=pending
{t(B_prov)} api-4 INFO provider POST /v1/charges order=88213 amount=4999
{t(A_ok)} api-2 INFO provider succeeded charge=ch_3PqA81 {A_took:.3f}s
{t(A_done)} api-2 INFO request done POST /api/orders/88213/pay 200 {A_done - A_in:.3f}s
{t(B_ok)} api-4 INFO provider succeeded charge=ch_3PqB27 {B_took:.3f}s
{t(B_done)} api-4 INFO request done POST /api/orders/88213/pay 200 {B_done - B_in:.3f}s
{t(C_conn)} api-1 INFO db connection order=88213 wait={C_wait:.2f}s
{t(C_read)} api-1 INFO pay order=88213 status_read=paid
{t(C_done)} api-1 INFO request done POST /api/orders/88213/pay 200 {C_done - C_in:.3f}s

== Card payment provider, charges with description "order 88213" (export from its dashboard) ==
charge_id   created   amount     status     idempotency_key
ch_3PqA81   14:22:14  49.99 EUR  succeeded  (none)
ch_3PqB27   14:22:25  49.99 EUR  succeeded  (none)

== PostgreSQL, this morning ==
=> SELECT id, status, payment_id, updated_at FROM orders WHERE id = 88213;
  id   | status | payment_id | updated_at
-------+--------+------------+-------------------
 88213 | paid   | ch_3PqB27  | {t(B_done - 0.001)}

=> SELECT order_id, charge_id, amount_cents, created_at FROM payments WHERE order_id = 88213 ORDER BY id;
 order_id | charge_id | amount_cents | created_at
----------+-----------+--------------+-------------------
    88213 | ch_3PqA81 |         4999 | {t(A_read - 0.002)}
    88213 | ch_3PqB27 |         4999 | {t(B_read - 0.002)}

=> SELECT n AS payment_rows, count(*) AS orders
   FROM (SELECT order_id, count(*) AS n FROM payments
         WHERE created_at >= '14:00' AND created_at < '15:00'  -- yesterday
         GROUP BY order_id) per_order
   GROUP BY n ORDER BY n;
 payment_rows | orders
--------------+--------
            1 |   {orders_paid}
            2 |     {twice}
            3 |      {thrice}

The browser received this body for the third attempt: {{"status":"paid","payment_id":"ch_3PqB27"}}
'''

DIAGRAM = '''Diagram.
Components (5): Browser (checkout page, web/checkout.js), Load balancer, API (4 instances, api-1 to api-4), PostgreSQL 17, Card payment provider API.
Connections: Browser (checkout page, web/checkout.js) -> Load balancer [POST /api/orders/{id}/pay]; Load balancer -> API (4 instances, api-1 to api-4) [round robin; idle timeout 10 s, then 504 to the browser]; API (4 instances, api-1 to api-4) -> PostgreSQL 17 [SQLAlchemy pool: 10 connections per instance, no overflow, waits up to 30 s for a free one]; API (4 instances, api-1 to api-4) -> Card payment provider API [POST /v1/charges, timeout 30 s].
Notes on the diagram: "PostgreSQL max_connections = 100"; "Provider latency, normal day: p50 0.9 s, p99 1.4 s"; "Yesterday 14:05 to 14:58: provider degraded (its status page)".
'''


def udiff(path, before, after):
    return f"diff --git a/{path} b/{path}\n" + "\n".join(difflib.unified_diff(
        before.splitlines(), after.splitlines(), f"a/{path}", f"b/{path}", n=3, lineterm=""))


PAYMENTS_PR = PAYMENTS.replace(
    "from fastapi import APIRouter, Depends, HTTPException",
    "from fastapi import APIRouter, Depends, Header, HTTPException").replace(
    "from app import provider\n", "from app import provider\nfrom app.cache import redis\n").replace(
    'log = logging.getLogger("payments")\n',
    'log = logging.getLogger("payments")\n\nIDEMPOTENCY_TTL_SECONDS = 60\n').replace(
    '''def pay(order_id: int, body: PayRequest, session: Session = Depends(get_session)):
''', '''def pay(
    order_id: int,
    body: PayRequest,
    idempotency_key: str = Header(...),
    session: Session = Depends(get_session),
):
    if redis.get(f"idem:{idempotency_key}"):
        raise HTTPException(409, "duplicate request")

''').replace(
    '''    session.add(Payment(order_id=order.id, charge_id=charge["id"], amount_cents=order.total_cents))
    return {"status": "paid", "payment_id": charge["id"]}''',
    '''    session.add(Payment(order_id=order.id, charge_id=charge["id"], amount_cents=order.total_cents))
    redis.set(f"idem:{idempotency_key}", "1", ex=IDEMPOTENCY_TTL_SECONDS)
    return {"status": "paid", "payment_id": charge["id"]}''')
CHECKOUT_PR = CHECKOUT.replace(
    '''      headers: { "Content-Type": "application/json" },''',
    '''      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },''')
assert PAYMENTS_PR.count("redis") == 3 and CHECKOUT_PR != CHECKOUT

TEST = '''from app.main import app
from fastapi.testclient import TestClient


def test_same_key_twice_returns_409(order_1_pending, provider_stub):
    client = TestClient(app)
    headers = {"Idempotency-Key": "k1"}
    r1 = client.post("/api/orders/1/pay", json={"card_token": "tok_test"}, headers=headers)
    r2 = client.post("/api/orders/1/pay", json={"card_token": "tok_test"}, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 409
    assert provider_stub.calls == 1
'''
test_diff = "diff --git a/tests/test_idempotency.py b/tests/test_idempotency.py\nnew file mode 100644\n--- /dev/null\n+++ b/tests/test_idempotency.py\n" + \
    f"@@ -0,0 +1,{len(TEST.splitlines())} @@\n" + "\n".join("+" + l if l else "+" for l in TEST.splitlines())

PR = '''Pull request: "Idempotent payments"

Description: Adds idempotency keys end to end. The checkout page sends an
Idempotency-Key header; the API remembers each key in Redis and rejects a
repeated key with 409, so a retried request can't charge twice. New test:
sending the same key twice returns 409 and the provider is called once.

Checks: 41 tests passed (the provider is a stub that answers at once).

''' + udiff("app/payments.py", PAYMENTS, PAYMENTS_PR) + "\n" + udiff("web/checkout.js", CHECKOUT, CHECKOUT_PR) + "\n" + test_diff + "\n"

# ---- the hour's dashboard -------------------------------------------------
pay_requests, lb_504 = 14910, 8530
window_s = 53 * 60
orders_rate = total_orders / window_s
pay_rate = pay_requests / window_s
p50 = 9.6
assert abs(orders_rate - 2.0) < 0.05 and abs(pay_rate - 4.7) < 0.05
assert pay_rate * p50 > 40 > orders_rate * p50  # retries push demand over 40 pooled connections

DASH = f'''A screenshot of the team's metrics dashboard for yesterday 13:30 to 15:30, one-minute points. A grey band marks 14:05 to 14:58. Five panels.

**1. Card provider, POST /v1/charges latency (seen from the API):** before 14:05, p50 0.9 s and p99 1.4 s. From 14:05 to 14:58, p50 {p50} s and p99 12.4 s. Back to normal at 14:59.

**2. POST /api/orders/{{id}}/pay requests received by the API, all instances:** about 2.0 per second before 14:05; about 4.7 per second from 14:05 to 14:58. Legend totals for 14:05 to 14:58: {pay_requests:,} requests, {total_orders:,} distinct orders, {lb_504:,} answered 504 by the load balancer.

**3. SQLAlchemy connection pool, per instance (checked out / size):** api-1 to api-4 all at 1 to 2 of 10 before 14:05; all four at 10 of 10 from 14:07 to 14:56. Pool wait time p99: 22.0 s. Error counter "QueuePool limit of size 10 overflow 0 reached, connection timed out, timeout 30.00": 1,840 in the window (all endpoints), each answered 500.

**4. PostgreSQL:** connections 40 of max_connections 100 from 14:07 to 14:56. By state, average over the window: "idle in transaction" 36, "active" 3, "idle" 1. CPU 12%. Lock waits: 0. Oldest open transaction, p99: 12.6 s.

**5. Other endpoints:** GET /api/orders/{{id}} p99 latency 80 ms before 14:05, 24.1 s during the window. GET /api/products error rate (5xx) 0.0% before, 9.2% during. Neither endpoint calls the card provider.

(For the interviewer: 4.7 pay requests per second, each holding a connection for about {p50} s, needs about {pay_rate * p50:.0f} connections; the four pools have 40. Without retries, 2.0 per second would need about {orders_rate * p50:.0f}.)
'''

PROPOSAL = '''# Proposal: charge cards in a background worker

Problem: the pay endpoint keeps the request open while the card provider
answers, so a slow provider means timeouts, retries and double charges.

## Design

1. `POST /api/orders/{id}/pay` sends a message `{"order_id": ..., "card_token": ...}`
   to the `charges` queue, then sets the order's status to `payment_processing`
   and commits. It answers 202 at once.
2. Workers (8 of them) receive messages. For each message: call
   `POST /v1/charges` (timeout 35 s), set the order to `paid` with the charge id,
   insert into `payments`, commit, then delete the message from the queue.
3. The checkout page polls `GET /api/orders/{id}` every 2 s until the status is
   `paid` or `failed`.

## Queue settings

| Setting | Value |
|---|---|
| Delivery | at least once |
| Visibility timeout | 30 s: a received message is hidden from other workers for 30 s; if it has not been deleted by then, it is delivered again |
| Max receives | 5, then the message moves to the dead-letter queue |
| Retention | 4 days |

## Why this fixes double charges

The queue guarantees that every message is processed, and only a worker
charges cards, so the browser's retries can no longer create a second charge.

## Rollout

Next sprint. No change to the provider integration (`app/provider.py`).
'''

entities = [
    repo_entity("e1", "payments-api", files),
    excalidraw_entity("e2", "request-path.excalidraw", DIAGRAM),
    code_entity("e3", "order-88213-logs.txt", LOGS),
    code_entity("e4", "pr-idempotent-payments.diff", PR),
    image_entity("e5", "incident-dashboard.png", DASH),
    md_entity("e6", "proposal-charge-worker.md", PROPOSAL),
]

p3 = probe(
    1,
    "The team proposes moving charging to a background worker. Show proposal-charge-worker.md. Ask whether the design removes double charges as it claims, what can still charge a card twice, and what they would change before approving it. If they ask whether the provider can recognise a repeated request: yes, as the docstring in provider.py says, for 24 hours. If they ask whether the queue can extend a message's visibility timeout while a worker is busy: yes. If they ask about the card token: tokens are single-use and expire after 10 minutes. If they ask how many orders a minute at peak: about 120.",
    "It moves the problem; it does not remove it. Delivery is at least once, so a message can be processed twice by design: \"every message is processed\" is not \"processed once\". Worse, the visibility timeout (30 s) is shorter than the provider timeout (35 s): when the provider is slow, as yesterday, the message becomes visible again while the first worker is still waiting, a second worker charges again, and with max receives 5 a card can be charged up to five times: the same mistake as the 10-second load balancer in front of a 30-second provider call. A worker that crashes after the provider succeeds but before it commits and deletes also gets the message redelivered. Step 1 sends the message, then commits: if the commit fails, a charge happens for an order that was never marked; if the browser's retry (checkout.js still retries 5xx) reaches the endpoint twice, two messages are sent for one order and nothing deduplicates them. \"No change to the provider integration\" keeps the missing piece missing. To approve: a payment attempt row created in the same transaction as the status change (a transactional outbox: the row is the message, a relay publishes it), with a unique constraint so one order has one active attempt; the worker claims the attempt with a conditional update (status 'processing' only if still 'pending'); every provider call carries an idempotency key derived from the attempt id, so any redelivery gets the first charge back from the provider; provider timeout well under the visibility timeout, or the worker extends visibility while it waits; a timeout is an unknown outcome, so the worker asks the provider (by idempotency key) rather than charging blindly; a reconciliation job compares the provider's charges with the payments table daily and alerts; dead-letter messages alert someone. Also: card tokens in the queue for 4 days are both sensitive and useless after 10 minutes; keep the token only as long as needed. Use this for yesterday's 41 orders: reconcile and refund the extra charges.",
    ["processed twice by design", "shorter than the provider timeout", "transactional outbox"],
    ["Compare the visibility timeout with the time a worker may spend on one message.",
     "A worker gets the charge back from the provider and then crashes before it deletes the message. What happens next?",
     "Which part of the system would recognise a repeated charge for the same order?"],
    3, ["e6"])

p2 = probe(
    1,
    "Show incident-dashboard.png for the same hour. Ask what it shows, why endpoints that never call the card provider failed too, and how they would restructure the pay handler. If they ask whether PostgreSQL was the bottleneck: show nothing new; ask what the dashboard says about it. If they ask whether they can raise the pool size: max_connections is 100 and other services use about 30 of them.",
    "Every pay request holds a pooled connection and an open transaction for the whole provider call: session.connection() begins the transaction at the start of the handler, the provider call happens inside it, and the commit waits for the handler to return. So PostgreSQL shows 36 of 40 connections idle in transaction, CPU at 12% and no lock waits: the database is idle, the pool is the limit. Little's law: 4.7 requests per second times about 9.6 s held is about 45 connections against 40; at 2.0 per second without retries it would have been about 19, so the retries pushed demand over the pool, and each retry added load while its earlier attempt was still holding a connection. GET /api/orders and GET /api/products share the same pools, so they waited up to 30 s for a connection (p99 wait 22 s) and 1,840 requests failed with the QueuePool timeout. Restructure: never hold a transaction across the network call. Short transaction 1: claim the order with a conditional update (pending to charging, only if still pending) and create the payment attempt, commit. Then call the provider with no connection held, using an idempotency key from the attempt. Short transaction 2: record the result (paid or failed). Also: provider timeout below the load balancer's 10 s, or answer 202 and let the page poll; a separate small pool, or a concurrency limit, for pay so it can't starve reads (a bulkhead); a circuit breaker when the provider is degraded; checkout.js backs off and stops retrying a 504 blindly. Raising the pool size moves the limit: 4 instances times 25 would take all 100 connections.",
    ["idle in transaction", "across the network call", "pushed demand over the pool"],
    ["What is each pay request doing with its connection while it waits for the provider?",
     "Multiply the pay request rate by how long each one holds a connection. Compare it with the pool.",
     "Why would GET /api/products fail during this hour?"],
    2, ["e5"], nxt=[p3])

p1 = probe(
    1,
    "A teammate opened a pull request to stop double charges. Show the diff. Ask them to review it as they would on the team: what happens to yesterday's order 88213 with this change, what each part does under retries and concurrent requests, and what they would ask for instead. If they ask what checkout.js does with a 409: the same as any 4xx, it shows the response text to the customer. If they ask what Redis is used for already: sessions and rate limits; it is a single primary with a replica. If they ask how quickly the browser retries: at once, with no delay.",
    "It wouldn't have saved order 88213. checkout.js calls crypto.randomUUID() inside the loop, so it sends a new key on every attempt: the retry is a different key and the server can't recognise it. Even with one key, the key is stored only after the charge succeeds, 11 s later, so a retry arriving during the provider call finds nothing in Redis and charges again: the same race as before, moved. redis.get followed later by redis.set is not atomic either; two requests can both pass the get. A duplicate gets 409 \"duplicate request\", and checkout.js shows that text to the customer as an error although they paid; a repeat should get the first request's stored response (same status and body), or a 409 meaning 'still in progress, retry later' while it is running. The 60-second TTL is shorter than a retry sequence can take with a slow provider and much shorter than the provider's 24 hours. The key isn't scoped to the order or checked against the request body, so a reused key on another order is rejected. The provider still gets no idempotency key, though provider.py supports one. The test sends two requests one after the other against a stub that answers at once, so it can't show the race. Ask for: the key created once per Pay press, before the loop, and reused on every retry; the server claims (order, key) atomically before charging (SET NX with an in-progress value, or an insert into an idempotency table with a unique constraint) and records the result with the stored response to replay it; the same key, or one derived from the payment attempt, passed to create_charge so the provider deduplicates too; a conditional update on the order (status 'charging' only if still 'pending') and a unique constraint so one order can't have two successful payments; a test with two concurrent requests and a slow provider stub.",
    ["new key on every attempt", "claims (order, key) atomically", "stored response"],
    ["Follow the second attempt for order 88213 through the new code. What key does it carry, and what is in Redis when it arrives?",
     "What does the customer see when a retry gets 409?",
     "What would the test have to do to show a retry arriving during the provider call?"],
    3, ["e4"], nxt=[p2])

question = {
    "name": "How one order's card was charged twice",
    "mode": "open-probe",
    "topics": [
        "Idempotency and safe retries for a payment endpoint",
        "Transactions and check-then-act races in a web API (PostgreSQL, SQLAlchemy)",
        "Timeouts, connection pools and queues under a slow dependency",
    ],
    "seniority": "senior",
    "duration": 12,
    "status": "draft",
    "seed_question": "Yesterday between 14:05 and 14:58, **41 orders** were charged two or three times on the customer's card. During that hour the card payment provider was slow. The checkout's Pay button calls one endpoint in a Python web API (FastAPI, SQLAlchemy, PostgreSQL), which runs as four instances behind a load balancer.\n\nAttached: the service's code, a diagram of the request path with its timeouts, and the logs for one affected order, 88213.\n\n**How did order 88213 get charged twice? Walk through the timeline and point to the code.**",
    "entity_refs": [{"id": "e1", "run": None, "editable": False},
                    {"id": "e2", "run": None, "editable": False},
                    {"id": "e3", "run": None, "editable": False}],
    "mcq_choices": [],
    "question_prompt": "Senior backend engineer, 5 to 8 years, who builds web APIs that take money. The question follows one pay endpoint that calls a card provider inside a request-long database transaction: how one order was charged twice when the provider was slow, a teammate's idempotency-key pull request, a dashboard of the hour showing the connection pools exhausted, and a proposal to move charging to a queue worker. The first probe is the richest (the pull request: the key made per attempt, the key stored after the charge, the 409, the TTL, the provider left without a key); the last is the hardest (judging a queue design whose visibility timeout is shorter than its provider timeout and whose enqueue is outside the transaction). Press for answers grounded in the files. Strong candidates name specific things: the 504 at 10.001 s from the load balancer while api-2 kept going and charged at 11.771 s; checkout.js retrying any 5xx at once; api-4's status_read=pending at 14:22:13.8 while api-2 was still in the provider call; `if order.status == \"paid\"` then the charge with nothing in between that stops a second request; create_charge called without the idempotency_key it accepts; the orders row ending with ch_3PqB27 while the browser was told ch_3PqB27 and both charges exist; the payments created_at values equal to the transaction start times (14:22:03.122, 14:22:13.789), which show the transaction spanned the provider call; the 7.38 s pool wait on api-1; no unique constraint on payments.order_id; the 41 orders in the SQL result. In later stages: crypto.randomUUID() inside the loop, redis.set after the charge, 36 connections idle in transaction, 4.7 vs 2.0 requests per second, the 30 s visibility timeout against the 35 s provider timeout. If an answer names nothing from the files, ask for one line or one number before moving on. If they ask what isolation level PostgreSQL uses: the default, read committed. If they ask whether the customer pressed Pay more than once: no, one press; the three requests are checkout.js. Don't explain idempotency keys, check-then-act races, isolation levels, connection pooling or at-least-once delivery to the candidate.",
    "answer_key": {
        "red_flags": [
            "proposes disabling the Pay button after one press as the fix, though the log shows one press and three requests from checkout.js",
            "proposes raising the load balancer timeout as the fix, or blames the provider for creating the second charge",
            "says 'wrap it in a transaction' though the handler already runs in one, without seeing that the second request read the row before the first committed",
        ],
        "required_concepts": [
            "The provider took 11.8 s, the load balancer gives up after 10 s and answers 504, but api-2 kept running and charged the card (ch_3PqA81): a 504 does not mean the charge failed, it means the load balancer stopped waiting. The provider client's own timeout is 30 s.",
            "checkout.js retries any 5xx at once with nothing that marks it as the same payment, so the retry reached api-4 while api-2 was still waiting on the provider and had not committed. The handler's check-then-act (`if order.status == \"paid\"`, then charge) read pending and charged again (ch_3PqB27): no row lock or conditional update, and create_charge is called without the idempotency key provider.py supports, so the provider can't recognise the repeat either.",
            "The data now disagree: the second request's commit overwrote orders.payment_id with ch_3PqB27, payments has two rows for 88213 (no unique constraint on order_id), and the third attempt, after a 7.38 s wait for a pool connection, read paid and told the browser ch_3PqB27. Both charges exist at the provider. 37 orders were charged twice and 4 three times the same way.",
        ],
        "good_additional_points": [
            "payments.created_at is PostgreSQL's now(), the transaction start (14:22:03.122 and 14:22:13.789), which shows each transaction stayed open across the provider call",
            "the third attempt waited 7.38 s for a pool connection: the pools were full, a sign of the next problem",
            "timeouts are ordered wrongly: the inner call (30 s) outlives the outer one (10 s), so the work continues after the caller has given up",
            "three charges happen when both retries read pending before the first commit",
            "the 41 orders need reconciliation against the provider's records and refunds of the extra charges",
            "checkout.js should back off between retries and treat a 504 on a payment as 'unknown', not 'failed'",
        ],
    },
    "probes": [p1],
    "seed_hints": hints([
        "Put the load balancer's three lines next to api-2's log lines. What was api-2 doing when the browser got its 504?",
        "When api-4 read the order at 14:22:13.8, had api-2's transaction committed?",
        "provider.py's create_charge accepts an argument the handler never passes. What is it for?",
    ]),
    "withheld_solution_parts": ["504 does not mean", "check-then-act", "idempotency key"],
    "max_probes": 3,
    "seed_duration": 4,
    "description_sections": {
        "task": "When a shop's card payment provider was slow for an hour, 41 customers were charged two or three times for one order. The candidate reads the code of the service behind the Pay button and the logs for one order, and explains step by step how the second charge happened. Then they review a colleague's fix, read the hour's system charts to explain why other pages failed too, and judge a plan to move card charging to a background job.",
        "signal": "Can this person trace a double charge through retries, timeouts and a database transaction from the logs and code, and design a payment endpoint that is safe to retry?",
        "audience": "Senior backend engineers (5 to 8 years) who build web services that handle payments or other actions that must happen once. Knowing Python, PostgreSQL, HTTP timeouts and retries, and message queues helps.",
        "implement": "1. Explains, from the code, a diagram and one order's logs, how the card was charged twice. *(4 min)*\n2. Reviews a colleague's fix for repeated requests and says whether it would have stopped this. *(3 min)*\n3. Reads the system's charts for that hour, explains why pages that don't take payments failed too, and says how to change the payment code. *(2 min)*\n4. Judges a plan to charge cards in a background job, and says what could still charge a card twice. *(3 min)*",
        "starting_state": "- The payment service's code (a small code folder), including the checkout page's script\n- A diagram of how a payment request travels, with each part's time limit\n- The logs for one affected order: the load balancer's, the service's, the payment provider's and the database's\n- Later: a colleague's code change, a screenshot of the hour's system charts, and a colleague's design for charging in a background job",
    },
    "seed_highlights": [
        {"entity_id": "e1", "path": "app/payments.py",
         "start_line": line_of(PAYMENTS, "@router.post(\"/api/orders/{order_id}/pay\")"),
         "end_line": line_of(PAYMENTS, "def pay(order_id")},
    ],
}

check_and_write("new-be-1", question, entities)
print(LOGS)
