"""Hand-written sample pull requests for exploring the dashboard without an LLM API key.

Every repository, author and pull request here is fictional (owner ``reviewmind-demo``), and
every finding was written by hand to match the code it points at — none of it is model output.
Sample reviews are stored with ``is_sample = true`` and labelled as such in the UI.
"""

from dataclasses import dataclass, field

DEMO_OWNER = "reviewmind-demo"


def tabs(code: str) -> str:
    """Go source is written here with 4-space indents for readability; gofmt uses tabs."""
    lines = []
    for line in code.split("\n"):
        stripped = line.lstrip(" ")
        depth = (len(line) - len(stripped)) // 4
        lines.append("\t" * depth + stripped)
    return "\n".join(lines)


@dataclass(frozen=True)
class SampleFinding:
    anchor: str
    severity: str
    category: str
    title: str
    comment: str
    suggested_fix: str | None = None
    confidence: str = "high"
    status: str = "open"
    span: int = 0


@dataclass(frozen=True)
class SampleFile:
    filename: str
    status: str = "modified"
    after: str = ""
    before: str = ""
    summary: str = ""
    findings: tuple[SampleFinding, ...] = ()
    # Lockfiles and assets only need a size; they are skipped before review anyway.
    skipped_size: tuple[int, int] | None = None


@dataclass(frozen=True)
class SampleReview:
    repo: str
    number: int
    title: str
    body: str
    author: str
    head_ref: str
    days_ago: float
    files: tuple[SampleFile, ...]
    merged: bool = False
    retry_file: str | None = None
    commits: int = 3


SAMPLE_REPOS = {
    "payments-api": {
        "description": "Payment processing service: charges, refunds and merchant payouts.",
        "language": "Python",
        "stars": 214,
    },
    "web-dashboard": {
        "description": "Customer analytics dashboard built with React and TypeScript.",
        "language": "TypeScript",
        "stars": 128,
    },
    "edge-cache": {
        "description": "Distributed edge cache with TTL eviction and consistent-hash sharding.",
        "language": "Go",
        "stars": 902,
    },
}


# --- payments-api #142: partial refunds (first push) -------------------------------------

REFUNDS_V1 = '''from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import current_merchant
from app.db import get_connection
from app.services.ledger import record_refund

router = APIRouter(prefix="/refunds", tags=["refunds"])


class RefundRequest(BaseModel):
    charge_id: str
    amount: float
    reason: str | None = None


@router.post("")
async def create_refund(body: RefundRequest, merchant=Depends(current_merchant)):
    conn = await get_connection()
    charge = await conn.fetchrow(
        f"SELECT id, merchant_id, amount, refunded FROM charges WHERE id = '{body.charge_id}'"
    )
    if charge is None:
        raise HTTPException(404, "Charge not found")

    remaining = charge["amount"] - charge["refunded"]
    if body.amount > remaining:
        raise HTTPException(400, "Refund exceeds the refundable amount")

    await conn.execute(
        "UPDATE charges SET refunded = refunded + $1 WHERE id = $2",
        body.amount,
        body.charge_id,
    )
    await record_refund(conn, charge["id"], body.amount, body.reason)
    return {"charge_id": charge["id"], "refunded": body.amount}
'''

LEDGER_BEFORE = '''import logging

logger = logging.getLogger(__name__)


async def record_charge(conn, charge_id, amount):
    await conn.execute(
        "INSERT INTO ledger (charge_id, kind, amount) VALUES ($1, 'charge', $2)",
        charge_id,
        amount,
    )


async def merchant_balance(conn, merchant_id):
    rows = await conn.fetch("SELECT amount FROM ledger WHERE merchant_id = $1", merchant_id)
    return sum(row["amount"] for row in rows)
'''

LEDGER_AFTER = '''import logging

logger = logging.getLogger(__name__)


async def record_charge(conn, charge_id, amount):
    await conn.execute(
        "INSERT INTO ledger (charge_id, kind, amount) VALUES ($1, 'charge', $2)",
        charge_id,
        amount,
    )


async def record_refund(conn, charge_id, amount, reason=None):
    try:
        await conn.execute(
            "INSERT INTO ledger (charge_id, kind, amount, note) VALUES ($1, 'refund', $2, $3)",
            charge_id,
            -amount,
            reason,
        )
    except Exception:
        logger.warning("Could not record refund for %s", charge_id)


async def merchant_balance(conn, merchant_id):
    rows = await conn.fetch("SELECT amount FROM ledger WHERE merchant_id = $1", merchant_id)
    return sum(row["amount"] for row in rows)


async def refund_totals(conn, charge_ids):
    totals = {}
    for charge_id in charge_ids:
        row = await conn.fetchrow(
            "SELECT COALESCE(SUM(-amount), 0) AS total FROM ledger WHERE charge_id = $1 AND kind = 'refund'",
            charge_id,
        )
        totals[charge_id] = row["total"]
    return totals
'''

MAIN_BEFORE = '''from fastapi import FastAPI

from app.routes import charges, payouts

app = FastAPI(title="Payments API")
app.include_router(charges.router)
app.include_router(payouts.router)
'''

MAIN_AFTER = '''from fastapi import FastAPI

from app.routes import charges, payouts, refunds

app = FastAPI(title="Payments API")
app.include_router(charges.router)
app.include_router(payouts.router)
app.include_router(refunds.router)
'''

# --- payments-api #142: partial refunds (after review fixes) -----------------------------

REFUNDS_V2 = '''from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import current_merchant
from app.db import get_connection
from app.services.ledger import record_refund

router = APIRouter(prefix="/refunds", tags=["refunds"])


class RefundRequest(BaseModel):
    charge_id: str
    amount: Decimal = Field(gt=0)
    reason: str | None = None


@router.post("")
async def create_refund(body: RefundRequest, merchant=Depends(current_merchant)):
    conn = await get_connection()
    async with conn.transaction():
        charge = await conn.fetchrow(
            "SELECT id, merchant_id, amount, refunded FROM charges WHERE id = $1 FOR UPDATE",
            body.charge_id,
        )
        if charge is None or charge["merchant_id"] != merchant.id:
            raise HTTPException(404, "Charge not found")

        remaining = charge["amount"] - charge["refunded"]
        if body.amount > remaining:
            raise HTTPException(400, "Refund exceeds the refundable amount")

        await conn.execute(
            "UPDATE charges SET refunded = refunded + $1 WHERE id = $2",
            body.amount,
            body.charge_id,
        )
        await record_refund(conn, charge["id"], body.amount, body.reason)
    return {"charge_id": charge["id"], "refunded": str(body.amount)}
'''

REFUND_TESTS = '''from decimal import Decimal

import pytest


async def test_refund_cannot_exceed_remaining_amount(client, charge):
    response = await client.post("/refunds", json={"charge_id": charge.id, "amount": "150.00"})
    assert response.status_code == 400


async def test_merchants_cannot_refund_each_others_charges(client_for, charge, other_merchant):
    response = await client_for(other_merchant).post("/refunds", json={"charge_id": charge.id, "amount": "1.00"})
    assert response.status_code == 404


async def test_partial_refunds_accumulate(client, charge, ledger):
    await client.post("/refunds", json={"charge_id": charge.id, "amount": "10.00"})
    await client.post("/refunds", json={"charge_id": charge.id, "amount": "15.50"})
    assert await ledger.refunded(charge.id) == Decimal("25.50")


@pytest.mark.parametrize("amount", ["0", "-5"])
async def test_rejects_non_positive_amounts(client, charge, amount):
    response = await client.post("/refunds", json={"charge_id": charge.id, "amount": amount})
    assert response.status_code == 422
'''

# --- web-dashboard #87: live revenue chart -----------------------------------------------

REVENUE_CHART = '''import { useEffect, useState } from 'react'
import { fetchRevenue, type RevenuePoint } from '../api/revenue'
import { formatCurrency } from '../lib/format'

interface Props {
  accountId: string
  range: '7d' | '30d' | '90d'
}

export function RevenueChart({ accountId, range }: Props) {
  const [points, setPoints] = useState<RevenuePoint[]>([])
  const [hovered, setHovered] = useState<RevenuePoint | null>(null)

  useEffect(() => {
    fetchRevenue(accountId, range).then(setPoints)
    setInterval(() => {
      fetchRevenue(accountId, range).then(setPoints)
    }, 5000)
  })

  const max = Math.max(...points.map((p) => p.amount))

  return (
    <div className="revenue-chart">
      <svg viewBox="0 0 600 200" role="img" aria-label="Revenue over time">
        {points.map((point, index) => (
          <rect
            key={point.date}
            x={index * (600 / points.length)}
            y={200 - (point.amount / max) * 200}
            width={600 / points.length - 2}
            height={(point.amount / max) * 200}
            onMouseEnter={() => setHovered(point)}
          />
        ))}
      </svg>
      {hovered && (
        <div
          className="tooltip"
          dangerouslySetInnerHTML={{ __html: `${hovered.label}: ${formatCurrency(hovered.amount)}` }}
        />
      )}
    </div>
  )
}
'''

REVENUE_API_BEFORE = '''export interface RevenuePoint {
  date: string
  amount: number
}

export async function fetchRevenue(accountId: string): Promise<RevenuePoint[]> {
  const response = await fetch(`/api/accounts/${accountId}/revenue`)
  return response.json()
}
'''

REVENUE_API_AFTER = '''export interface RevenuePoint {
  date: string
  label: string
  amount: number
}

export async function fetchRevenue(accountId: string, range: string): Promise<RevenuePoint[]> {
  const response = await fetch(`/api/accounts/${accountId}/revenue?range=${range}`)
  const data: any = await response.json()
  return data.points
}
'''

# --- edge-cache #311: TTL eviction -------------------------------------------------------

EVICT_GO = tabs('''package cache

import (
    "log"
    "time"
)

// StartEvictor removes expired entries every interval until stop is closed.
func (c *Cache) StartEvictor(interval time.Duration, stop <-chan struct{}) {
    ticker := time.NewTicker(interval)
    go func() {
        for {
            select {
            case <-ticker.C:
                c.evictExpired()
            case <-stop:
                return
            }
        }
    }()
}

func (c *Cache) evictExpired() {
    removed := 0
    for key, entry := range c.items {
        if time.Now().After(entry.expiresAt) {
            delete(c.items, key)
            removed++
        }
    }
    if removed > 0 {
        log.Printf("evicted %d expired entries", removed)
    }
}
''')

CACHE_GO_BEFORE = tabs('''package cache

import "sync"

type entry struct {
    value []byte
}

type Cache struct {
    mu    sync.RWMutex
    items map[string]entry
}

func New() *Cache {
    return &Cache{items: make(map[string]entry)}
}
''')

CACHE_GO_AFTER = tabs('''package cache

import (
    "sync"
    "time"
)

type entry struct {
    value     []byte
    expiresAt time.Time
}

type Cache struct {
    mu    sync.RWMutex
    items map[string]entry
}

func New() *Cache {
    return &Cache{items: make(map[string]entry)}
}

func (c *Cache) Set(key string, value []byte, ttl time.Duration) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.items[key] = entry{value: value, expiresAt: time.Now().Add(ttl)}
}
''')

# --- payments-api #150: webhook retries --------------------------------------------------

WEBHOOKS_BEFORE = '''import logging

import httpx

logger = logging.getLogger(__name__)


async def deliver(event, endpoint):
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(endpoint.url, json=event.payload)
    return response.status_code < 300
'''

WEBHOOKS_AFTER = '''import hashlib
import hmac
import logging
import time

import httpx

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6


def sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def deliver(event, endpoint):
    body = event.payload_bytes()
    signature = sign(body, endpoint.secret)
    headers = {"X-Signature": signature, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = await client.post(endpoint.url, content=body, headers=headers)
            if response.status_code < 300:
                return True
            logger.info("Delivery to %s failed (%s), secret=%s", endpoint.url, response.status_code, endpoint.secret)
            time.sleep(2**attempt)
    return False
'''

WEBHOOK_TESTS = '''import pytest

from app.workers.webhooks import sign


def test_signature_is_stable():
    assert sign(b"{}", "secret") == sign(b"{}", "secret")


def test_signature_depends_on_secret():
    assert sign(b"{}", "a") != sign(b"{}", "b")
'''

# --- web-dashboard #91: useFilters hook --------------------------------------------------

USE_FILTERS = '''import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

export type Range = '7d' | '30d' | '90d'

const RANGES: Range[] = ['7d', '30d', '90d']

export function useFilters() {
  const [params, setParams] = useSearchParams()

  const range = useMemo<Range>(() => {
    const value = params.get('range')
    return RANGES.includes(value as Range) ? (value as Range) : '30d'
  }, [params])

  const setRange = useCallback(
    (next: Range) => {
      setParams((current) => {
        current.set('range', next)
        return current
      })
    },
    [setParams],
  )

  const segment = params.get('segment') ?? 'all'

  return { range, setRange, segment }
}
'''

OVERVIEW_BEFORE = '''import { useSearchParams } from 'react-router'
import { RevenueChart } from '../components/RevenueChart'

export function Overview({ accountId }: { accountId: string }) {
  const [params, setParams] = useSearchParams()
  const range = (params.get('range') as '7d' | '30d' | '90d') ?? '30d'

  return (
    <section>
      <RangePicker value={range} onChange={(next) => setParams({ range: next })} />
      <RevenueChart accountId={accountId} range={range} />
    </section>
  )
}
'''

OVERVIEW_AFTER = '''import { RevenueChart } from '../components/RevenueChart'
import { useFilters } from '../hooks/useFilters'

export function Overview({ accountId }: { accountId: string }) {
  const { range, setRange } = useFilters()

  return (
    <section>
      <RangePicker value={range} onChange={setRange} />
      <RevenueChart accountId={accountId} range={range} />
    </section>
  )
}
'''

USE_FILTERS_TEST = '''import { renderHook, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { useFilters } from './useFilters'

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter initialEntries={['/?range=bogus']}>{children}</MemoryRouter>
)

test('falls back to 30d for unknown ranges and updates the URL', () => {
  const { result } = renderHook(() => useFilters(), { wrapper })
  expect(result.current.range).toBe('30d')
  act(() => result.current.setRange('7d'))
  expect(result.current.range).toBe('7d')
})
'''

# --- edge-cache #318: admin endpoints ----------------------------------------------------

ADMIN_GO = tabs('''package http

import (
    "encoding/json"
    "net/http"

    "github.com/reviewmind-demo/edge-cache/internal/cache"
)

type statsResponse struct {
    Entries   int     `json:"entries"`
    HitRate   float64 `json:"hit_rate"`
    Evictions uint64  `json:"evictions"`
}

func RegisterAdmin(mux *http.ServeMux, c *cache.Cache) {
    mux.HandleFunc("/admin/stats", func(w http.ResponseWriter, r *http.Request) {
        stats := c.Stats()
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(statsResponse{
            Entries:   stats.Entries,
            HitRate:   float64(stats.Hits) / float64(stats.Hits+stats.Misses),
            Evictions: stats.Evictions,
        })
    })

    mux.HandleFunc("/admin/flush", func(w http.ResponseWriter, r *http.Request) {
        c.Flush()
        w.WriteHeader(http.StatusNoContent)
    })
}
''')

# --- web-dashboard #95: React 19 upgrade -------------------------------------------------

PACKAGE_JSON_BEFORE = '''{
  "name": "web-dashboard",
  "private": true,
  "version": "2.4.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router": "^6.26.2"
  },
  "devDependencies": {
    "@testing-library/react": "^14.3.1",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.6.2",
    "vite": "^5.4.8",
    "vitest": "^2.1.2"
  }
}
'''

PACKAGE_JSON_AFTER = '''{
  "name": "web-dashboard",
  "private": true,
  "version": "2.5.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "react-router": "^7.6.0"
  },
  "devDependencies": {
    "@testing-library/react": "^14.3.1",
    "@types/react": "^19.1.2",
    "@types/react-dom": "^19.1.2",
    "typescript": "^5.8.3",
    "vite": "^6.3.5",
    "vitest": "^3.1.4"
  }
}
'''

MAIN_TSX_BEFORE = '''import React from 'react'
import ReactDOM from 'react-dom'
import { App } from './App'
import './index.css'

ReactDOM.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
  document.getElementById('root'),
)
'''

MAIN_TSX_AFTER = '''import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
'''

# --- edge-cache #322: consistent hashing -------------------------------------------------

RING_GO = tabs('''package shard

import (
    "hash/crc32"
    "sort"
    "strconv"
)

type Ring struct {
    replicas int
    hashes   []uint32
    owners   map[uint32]string
}

func NewRing(replicas int, nodes ...string) *Ring {
    r := &Ring{replicas: replicas, owners: make(map[uint32]string)}
    for _, node := range nodes {
        for i := 0; i < replicas; i++ {
            h := crc32.ChecksumIEEE([]byte(strconv.Itoa(i) + node))
            r.hashes = append(r.hashes, h)
            r.owners[h] = node
        }
    }
    sort.Slice(r.hashes, func(i, j int) bool { return r.hashes[i] < r.hashes[j] })
    return r
}

func (r *Ring) Owner(key string) string {
    h := crc32.ChecksumIEEE([]byte(key))
    idx := sort.Search(len(r.hashes), func(i int) bool { return r.hashes[i] >= h })
    return r.owners[r.hashes[idx]]
}

func (r *Ring) Remove(node string) {
    for i := 0; i < r.replicas; i++ {
        h := crc32.ChecksumIEEE([]byte(strconv.Itoa(i) + node))
        delete(r.owners, h)
        for j, candidate := range r.hashes {
            if candidate == h {
                r.hashes = append(r.hashes[:j], r.hashes[j+1:]...)
                break
            }
        }
    }
}
''')

# --- payments-api #155: currency conversion ----------------------------------------------

FX_PY = '''from decimal import ROUND_HALF_UP, Decimal

import httpx

RATES_URL = "https://rates.example.com/latest"


async def get_rate(base: str, quote: str) -> Decimal:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(RATES_URL, params={"base": base})
        response.raise_for_status()
    return Decimal(str(response.json()["rates"][quote]))


async def convert(amount: Decimal, base: str, quote: str) -> Decimal:
    if base == quote:
        return amount
    rate = await get_rate(base, quote)
    converted = amount * rate
    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def convert_many(amounts: list[Decimal], base: str, quote: str) -> list[Decimal]:
    return [await convert(amount, base, quote) for amount in amounts]
'''

PAYOUTS_BEFORE = '''from fastapi import APIRouter

router = APIRouter(prefix="/payouts", tags=["payouts"])


@router.post("/{payout_id}/send")
async def send_payout(payout_id: str):
    payout = await load_payout(payout_id)
    await transfer(payout.destination, payout.amount)
    return {"status": "sent"}
'''

PAYOUTS_AFTER = '''from decimal import Decimal

from fastapi import APIRouter

from app.services.fx import convert

router = APIRouter(prefix="/payouts", tags=["payouts"])


@router.post("/{payout_id}/send")
async def send_payout(payout_id: str):
    payout = await load_payout(payout_id)
    amount = await convert(Decimal(payout.amount), payout.currency, payout.destination.currency)
    await transfer(payout.destination, amount)
    return {"status": "sent"}
'''


SAMPLE_REVIEWS: tuple[SampleReview, ...] = (
    SampleReview(
        repo="payments-api",
        number=142,
        title="Add partial refunds endpoint",
        body="Adds `POST /refunds` so merchants can refund part of a charge. Ledger entries are written for every refund.",
        author="maya-chen",
        head_ref="feature/partial-refunds",
        days_ago=52,
        files=(
            SampleFile(
                filename="app/routes/refunds.py",
                status="added",
                after=REFUNDS_V1,
                summary="New refund endpoint. The charge lookup is injectable and isn't scoped to the calling merchant, and the refund isn't atomic.",
                findings=(
                    SampleFinding(
                        anchor="f\"SELECT id, merchant_id",
                        severity="critical",
                        category="security",
                        title="SQL query built from request input",
                        comment="`body.charge_id` is interpolated straight into the SQL string, so a crafted id such as `x' OR '1'='1` changes the query. The UPDATE below already uses `$1` placeholders — this lookup should too.",
                        suggested_fix='        "SELECT id, merchant_id, amount, refunded FROM charges WHERE id = $1", body.charge_id',
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="if charge is None:",
                        severity="critical",
                        category="security",
                        title="Refunds aren't scoped to the calling merchant",
                        comment="The charge is looked up by id alone and `merchant` is never compared with `charge[\"merchant_id\"]`, so any authenticated merchant can refund another merchant's charges by guessing an id.",
                        suggested_fix='    if charge is None or charge["merchant_id"] != merchant.id:',
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="    amount: float",
                        severity="warning",
                        category="bug",
                        title="Money modelled as a float",
                        comment="Floats can't represent most decimal amounts exactly (`0.1 + 0.2` is `0.30000000000000004`), so repeated partial refunds drift away from the ledger. `Decimal` is already imported but unused.",
                        suggested_fix="    amount: Decimal",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="    await conn.execute(",
                        span=4,
                        severity="warning",
                        category="bug",
                        title="Charge update and ledger write aren't atomic",
                        comment="The charge row is updated before `record_refund` runs, outside a transaction. If the ledger insert fails the charge shows a refund the ledger never recorded, and two concurrent refunds can both pass the remaining-amount check.",
                        suggested_fix='    async with conn.transaction():\n        await conn.execute(\n            "UPDATE charges SET refunded = refunded + $1 WHERE id = $2 AND amount - refunded >= $1",\n            body.amount,\n            body.charge_id,\n        )',
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="async def create_refund",
                        severity="warning",
                        category="missing-test",
                        title="No tests for a money-moving endpoint",
                        comment="This adds an endpoint with several failure paths — unknown charge, over-refund, cross-merchant access — but no test file changes. Cover at least the over-refund guard and the ownership check.",
                        confidence="medium",
                        status="accepted",
                    ),
                ),
            ),
            SampleFile(
                filename="app/services/ledger.py",
                before=LEDGER_BEFORE,
                after=LEDGER_AFTER,
                summary="Adds refund ledger entries and a totals helper; ledger failures are swallowed.",
                findings=(
                    SampleFinding(
                        anchor="    except Exception:",
                        span=1,
                        severity="warning",
                        category="bug",
                        title="Ledger failures are logged and swallowed",
                        comment="If the insert fails, the endpoint still returns success and the ledger silently disagrees with `charges`. Re-raise after logging so the caller's transaction can roll back.",
                        suggested_fix='    except Exception:\n        logger.exception("Could not record refund for %s", charge_id)\n        raise',
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="    for charge_id in charge_ids:",
                        severity="warning",
                        category="performance",
                        title="One query per charge (N+1)",
                        comment="`refund_totals` makes a round trip for every id, so a payout report over 500 charges runs 500 queries. `WHERE charge_id = ANY($1) GROUP BY charge_id` returns the same totals in one.",
                        status="dismissed",
                    ),
                ),
            ),
            SampleFile(
                filename="app/main.py",
                before=MAIN_BEFORE,
                after=MAIN_AFTER,
                summary="Registers the refunds router.",
            ),
            SampleFile(filename="poetry.lock", skipped_size=(42, 8)),
        ),
    ),
    SampleReview(
        repo="payments-api",
        number=142,
        title="Add partial refunds endpoint",
        body="Adds `POST /refunds` so merchants can refund part of a charge.\n\nUpdated after review: parameterised lookup, merchant scoping, Decimal amounts, a transaction around the refund, and tests.",
        author="maya-chen",
        head_ref="feature/partial-refunds",
        days_ago=49,
        merged=True,
        commits=6,
        files=(
            SampleFile(
                filename="app/routes/refunds.py",
                status="added",
                after=REFUNDS_V2,
                summary="Refund endpoint now runs in a transaction with a row lock, scoped to the merchant, using Decimal amounts.",
                findings=(
                    SampleFinding(
                        anchor="    reason: str | None = None",
                        severity="info",
                        category="style",
                        title="Unbounded free-text refund reason",
                        comment="`reason` is stored in the ledger's `note` column without a length limit, so a client can send megabytes of text. `Field(max_length=500)` bounds it at validation time.",
                        suggested_fix="    reason: str | None = Field(default=None, max_length=500)",
                        confidence="medium",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="    async with conn.transaction():",
                        severity="warning",
                        category="bug",
                        title="Possible lock contention under concurrent refunds",
                        comment="`FOR UPDATE` holds the charge row for the whole transaction, including the ledger insert. Under heavy concurrent refunds on one charge this could queue requests; confirm the ledger write stays fast.",
                        confidence="low",
                        status="false_positive",
                    ),
                ),
            ),
            SampleFile(
                filename="tests/test_refunds.py",
                status="added",
                after=REFUND_TESTS,
                summary="Covers over-refunds, cross-merchant access, accumulation and invalid amounts.",
            ),
            SampleFile(
                filename="app/services/ledger.py",
                before=LEDGER_BEFORE,
                after=LEDGER_AFTER.replace(
                    '        logger.warning("Could not record refund for %s", charge_id)',
                    '        logger.exception("Could not record refund for %s", charge_id)\n        raise',
                ),
                summary="Ledger failures now propagate so the refund transaction rolls back.",
            ),
            SampleFile(filename="app/main.py", before=MAIN_BEFORE, after=MAIN_AFTER, summary="Registers the refunds router."),
            SampleFile(filename="poetry.lock", skipped_size=(42, 8)),
        ),
    ),
    SampleReview(
        repo="web-dashboard",
        number=87,
        title="Live-updating revenue chart",
        body="Polls revenue every 5 seconds and shows a tooltip on hover.",
        author="dev-sam",
        head_ref="feat/live-revenue",
        days_ago=45,
        merged=True,
        retry_file="src/components/RevenueChart.tsx",
        files=(
            SampleFile(
                filename="src/components/RevenueChart.tsx",
                status="added",
                after=REVENUE_CHART,
                summary="New polling revenue chart. The effect leaks intervals on every render and the tooltip renders API text as HTML.",
                findings=(
                    SampleFinding(
                        anchor="  useEffect(() => {",
                        span=5,
                        severity="critical",
                        category="bug",
                        title="Effect re-runs on every render and stacks intervals",
                        comment="The effect has no dependency array, so it runs after every render — and every `setPoints` causes a render. Each run starts another 5-second interval that is never cleared, so polling multiplies until the tab stalls.",
                        suggested_fix="  useEffect(() => {\n    const load = () => fetchRevenue(accountId, range).then(setPoints)\n    load()\n    const timer = setInterval(load, 5000)\n    return () => clearInterval(timer)\n  }, [accountId, range])",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="dangerouslySetInnerHTML",
                        span=1,
                        severity="critical",
                        category="security",
                        title="Tooltip renders API text as HTML (XSS)",
                        comment="`hovered.label` comes from the revenue API, where labels are merchant-editable. Injecting it with `dangerouslySetInnerHTML` lets a label like `<img src=x onerror=…>` run script in every viewer's session. Render it as text.",
                        suggested_fix="        >\n          {hovered.label}: {formatCurrency(hovered.amount)}\n        </div>",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="const max = Math.max",
                        severity="warning",
                        category="bug",
                        title="Bars become NaN for empty or all-zero data",
                        comment="With no points `Math.max()` returns `-Infinity`, and with all-zero revenue it returns `0` — either way every bar's `y` and `height` are `NaN` and the chart renders nothing.",
                        suggested_fix="  const max = Math.max(1, ...points.map((p) => p.amount))",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="onMouseEnter={() => setHovered(point)}",
                        severity="info",
                        category="bug",
                        title="Tooltip never hides",
                        comment="There's no `onMouseLeave`, so the last hovered value stays on screen after the pointer leaves the chart.",
                        suggested_fix="            onMouseEnter={() => setHovered(point)}\n            onMouseLeave={() => setHovered(null)}",
                        confidence="medium",
                        status="accepted",
                    ),
                ),
            ),
            SampleFile(
                filename="src/api/revenue.ts",
                before=REVENUE_API_BEFORE,
                after=REVENUE_API_AFTER,
                summary="Adds a range parameter and point labels; HTTP errors are parsed as data.",
                findings=(
                    SampleFinding(
                        anchor="const data: any = await response.json()",
                        severity="warning",
                        category="bug",
                        title="HTTP errors are parsed as revenue data",
                        comment="`fetch` doesn't reject on 4xx/5xx, so an error body is parsed and `data.points` is `undefined` — which reaches `points.map` in the chart and throws. Check `response.ok` first.",
                        suggested_fix="  if (!response.ok) throw new Error(`Revenue request failed: ${response.status}`)\n  const data = (await response.json()) as { points: RevenuePoint[] }",
                        status="accepted",
                    ),
                ),
            ),
            SampleFile(filename="package-lock.json", skipped_size=(118, 41)),
            SampleFile(filename="public/revenue-empty-state.svg", status="added", skipped_size=(24, 0)),
        ),
    ),
    SampleReview(
        repo="edge-cache",
        number=311,
        title="TTL-based eviction worker",
        body="Entries now carry an expiry; a background goroutine sweeps expired keys on an interval.",
        author="kenji-w",
        head_ref="ttl-eviction",
        days_ago=38,
        merged=True,
        files=(
            SampleFile(
                filename="internal/cache/evict.go",
                status="added",
                after=EVICT_GO,
                summary="Background sweeper for expired entries. It mutates the shared map without the cache lock.",
                findings=(
                    SampleFinding(
                        anchor="for key, entry := range c.items {",
                        severity="critical",
                        category="bug",
                        title="Map mutated without holding the cache lock",
                        comment="`evictExpired` runs on its own goroutine and ranges over and deletes from `c.items` without taking `c.mu`, while `Get` and `Set` use the same map under the lock. That's a data race that crashes with `concurrent map iteration and map write`.",
                        suggested_fix=tabs("    c.mu.Lock()\n    defer c.mu.Unlock()\n    for key, entry := range c.items {"),
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="case <-stop:",
                        span=1,
                        severity="warning",
                        category="bug",
                        title="Ticker is never stopped",
                        comment="When `stop` closes the goroutine returns, but the ticker keeps firing into a channel nobody reads, leaking its timer for the life of the process.",
                        suggested_fix=tabs("            case <-stop:\n                ticker.Stop()\n                return"),
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="if time.Now().After(entry.expiresAt) {",
                        severity="info",
                        category="performance",
                        title="Clock read once per entry",
                        comment="Calling `time.Now()` inside the loop costs a call per entry and judges entries against a moving clock mid-sweep. Capture `now := time.Now()` once before the loop.",
                        suggested_fix=tabs("        if now.After(entry.expiresAt) {"),
                        confidence="medium",
                        status="dismissed",
                    ),
                    SampleFinding(
                        anchor="func (c *Cache) StartEvictor",
                        severity="warning",
                        category="missing-test",
                        title="Eviction has no tests",
                        comment="Nothing verifies that expired entries are removed, live ones survive, or that closing `stop` ends the goroutine. A test with a short interval and `-race` would also have caught the locking bug.",
                        status="accepted",
                    ),
                ),
            ),
            SampleFile(
                filename="internal/cache/cache.go",
                before=CACHE_GO_BEFORE,
                after=CACHE_GO_AFTER,
                summary="Entries gain an expiry and `Set` takes a TTL.",
                findings=(
                    SampleFinding(
                        anchor="func (c *Cache) Set(",
                        severity="info",
                        category="bug",
                        title="A zero TTL expires immediately",
                        comment="`ttl` of `0` sets `expiresAt` to now, so the entry is removed on the next sweep. If zero is meant as \"no expiry\", handle it explicitly.",
                        confidence="low",
                        status="false_positive",
                    ),
                ),
            ),
            SampleFile(filename="go.sum", skipped_size=(6, 2)),
        ),
    ),
    SampleReview(
        repo="payments-api",
        number=150,
        title="Retry webhook deliveries with exponential backoff",
        body="Failed webhook deliveries are retried up to six times with exponential backoff, and payloads are now HMAC-signed.",
        author="lena-ortiz",
        head_ref="webhook-retries",
        days_ago=31,
        merged=True,
        files=(
            SampleFile(
                filename="app/workers/webhooks.py",
                before=WEBHOOKS_BEFORE,
                after=WEBHOOKS_AFTER,
                summary="Signed deliveries with retries. The backoff blocks the event loop and the signing secret is logged.",
                findings=(
                    SampleFinding(
                        anchor="secret=%s",
                        severity="critical",
                        category="security",
                        title="Webhook signing secret written to logs",
                        comment="The endpoint's signing secret is included in an info-level log line on every failed attempt. Anyone with log access can then forge validly signed webhooks for that merchant.",
                        suggested_fix='            logger.info("Delivery to %s failed (%s), attempt %d", endpoint.url, response.status_code, attempt)',
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="time.sleep(2**attempt)",
                        severity="warning",
                        category="performance",
                        title="Blocking sleep inside an async worker",
                        comment="`time.sleep` blocks the event loop, so while one endpoint backs off — up to 64 seconds on the last attempt — every other delivery on this worker stalls too. Use `await asyncio.sleep(...)`.",
                        suggested_fix="            await asyncio.sleep(2**attempt)",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="response = await client.post",
                        span=1,
                        severity="warning",
                        category="bug",
                        title="Network errors abort the retry loop",
                        comment="`client.post` raises `httpx.TransportError` on timeouts and refused connections — exactly the failures retries exist for — and nothing catches it, so the first timeout ends delivery.",
                        suggested_fix="            try:\n                response = await client.post(endpoint.url, content=body, headers=headers)\n            except httpx.TransportError:\n                response = None\n            if response is not None and response.status_code < 300:",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="for attempt in range(1, MAX_ATTEMPTS + 1):",
                        severity="info",
                        category="bug",
                        title="Retries have no jitter",
                        comment="Every failing delivery retries on the same 2, 4, 8… second schedule, so when an endpoint recovers from an outage it receives the backlog in synchronised waves. Add random jitter to the delay.",
                        confidence="medium",
                        status="dismissed",
                    ),
                ),
            ),
            SampleFile(
                filename="tests/test_webhooks.py",
                status="added",
                after=WEBHOOK_TESTS,
                summary="Tests for the signature helper.",
                findings=(
                    SampleFinding(
                        anchor="def test_signature_is_stable",
                        severity="warning",
                        category="missing-test",
                        title="The retry loop itself is untested",
                        comment="Both tests cover `sign`, but nothing exercises `deliver`: success on a later attempt, giving up after `MAX_ATTEMPTS`, or the backoff between attempts.",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="import pytest",
                        severity="info",
                        category="style",
                        title="Unused pytest import",
                        comment="`pytest` isn't referenced in this module.",
                        suggested_fix="",
                        confidence="high",
                        status="dismissed",
                    ),
                ),
            ),
        ),
    ),
    SampleReview(
        repo="web-dashboard",
        number=91,
        title="Extract filter state into a useFilters hook",
        body="Moves range parsing out of Overview into a reusable hook with validation and a test.",
        author="dev-sam",
        head_ref="refactor/use-filters",
        days_ago=24,
        merged=True,
        files=(
            SampleFile(
                filename="src/hooks/useFilters.ts",
                status="added",
                after=USE_FILTERS,
                summary="Validated range filter backed by the URL.",
                findings=(
                    SampleFinding(
                        anchor="current.set('range', next)",
                        severity="info",
                        category="bug",
                        title="Mutates the previous search params",
                        comment="The updater mutates and returns the same `URLSearchParams` it was given. Returning `new URLSearchParams(current)` avoids shared-state surprises if something else reads the previous value.",
                        confidence="medium",
                        status="accepted",
                    ),
                    SampleFinding(
                        anchor="const segment = params.get('segment')",
                        severity="info",
                        category="style",
                        title="Segment isn't validated like range",
                        comment="`range` is checked against an allow-list but `segment` accepts any string from the URL. Validating both the same way keeps the hook's contract consistent.",
                        confidence="medium",
                    ),
                ),
            ),
            SampleFile(filename="src/pages/Overview.tsx", before=OVERVIEW_BEFORE, after=OVERVIEW_AFTER, summary="Overview now uses the hook."),
            SampleFile(
                filename="src/hooks/useFilters.test.tsx",
                status="added",
                after=USE_FILTERS_TEST,
                summary="Tests the fallback range and URL updates.",
            ),
        ),
    ),
    SampleReview(
        repo="edge-cache",
        number=318,
        title="Expose admin stats and flush endpoints",
        body="Adds `/admin/stats` for dashboards and `/admin/flush` for incident response.",
        author="kenji-w",
        head_ref="admin-endpoints",
        days_ago=17,
        files=(
            SampleFile(
                filename="internal/http/admin.go",
                status="added",
                after=ADMIN_GO,
                summary="Stats and flush handlers. The flush endpoint is unauthenticated and the hit rate is NaN on a cold cache.",
                findings=(
                    SampleFinding(
                        anchor='mux.HandleFunc("/admin/flush"',
                        severity="critical",
                        category="security",
                        title="Unauthenticated endpoint can flush the whole cache",
                        comment="`/admin/flush` has no authentication and accepts any method, so anyone who can reach the service can wipe the cache with a single GET — an easy way to stampede the origin. Wrap it in the admin auth middleware and require POST.",
                    ),
                    SampleFinding(
                        anchor="HitRate:   float64(stats.Hits)",
                        severity="warning",
                        category="bug",
                        title="Hit rate is NaN before the first request",
                        comment="With no hits or misses the division is `0/0`, which is `NaN` — and `encoding/json` refuses to encode NaN, so the endpoint returns an empty 200 until traffic arrives.",
                    ),
                    SampleFinding(
                        anchor="json.NewEncoder(w).Encode(statsResponse{",
                        severity="info",
                        category="bug",
                        title="Encoding errors are ignored",
                        comment="The error from `Encode` is discarded, which is how the NaN case above fails silently. Log it, or check it and return a 500.",
                    ),
                    SampleFinding(
                        anchor="func RegisterAdmin",
                        severity="warning",
                        category="missing-test",
                        title="Admin handlers have no tests",
                        comment="Neither handler is tested. A table test covering a cold cache and an unauthenticated flush would pin down both issues above.",
                        confidence="medium",
                    ),
                ),
            ),
        ),
    ),
    SampleReview(
        repo="web-dashboard",
        number=95,
        title="Upgrade to React 19",
        body="Bumps React, React Router and the toolchain; migrates to `createRoot`.",
        author="lena-ortiz",
        head_ref="chore/react-19",
        days_ago=11,
        merged=True,
        files=(
            SampleFile(
                filename="package.json",
                before=PACKAGE_JSON_BEFORE,
                after=PACKAGE_JSON_AFTER,
                summary="Dependency upgrades for React 19.",
                findings=(
                    SampleFinding(
                        anchor='"@testing-library/react": "^14.3.1"',
                        severity="warning",
                        category="bug",
                        title="Testing Library still on a React 18 major",
                        comment="`@testing-library/react` 14 declares a React 18 peer dependency, so installs warn and `renderHook` behaves differently under React 19. Version 16 supports React 19.",
                        suggested_fix='    "@testing-library/react": "^16.3.0",',
                        confidence="medium",
                        status="accepted",
                    ),
                ),
            ),
            SampleFile(
                filename="src/main.tsx",
                before=MAIN_TSX_BEFORE,
                after=MAIN_TSX_AFTER,
                summary="Migrates from `ReactDOM.render` to `createRoot`.",
                findings=(
                    SampleFinding(
                        anchor="createRoot(document.getElementById('root')!)",
                        severity="info",
                        category="style",
                        title="Non-null assertion hides a missing mount node",
                        comment="If `#root` is ever renamed, `!` turns a clear error into an opaque crash inside React. An explicit check with a message is kinder to the next person.",
                        confidence="medium",
                    ),
                ),
            ),
            SampleFile(filename="package-lock.json", skipped_size=(912, 604)),
        ),
    ),
    SampleReview(
        repo="edge-cache",
        number=322,
        title="Consistent-hash ring for shard routing",
        body="Routes keys to shards with a CRC32 ring and virtual nodes, so adding a node only moves a fraction of keys.",
        author="kenji-w",
        head_ref="hash-ring",
        days_ago=6,
        retry_file="internal/shard/ring.go",
        files=(
            SampleFile(
                filename="internal/shard/ring.go",
                status="added",
                after=RING_GO,
                summary="Hash ring with virtual nodes. Lookups past the last hash panic, and hash collisions silently reassign replicas.",
                findings=(
                    SampleFinding(
                        anchor="return r.owners[r.hashes[idx]]",
                        severity="critical",
                        category="bug",
                        title="Index out of range for keys past the last hash",
                        comment="`sort.Search` returns `len(r.hashes)` when a key hashes above every point on the ring, and indexing with it panics. A ring wraps around — those keys belong to the first point.",
                        suggested_fix=tabs("    return r.owners[r.hashes[idx%len(r.hashes)]]"),
                    ),
                    SampleFinding(
                        anchor="r.owners[h] = node",
                        severity="warning",
                        category="bug",
                        title="Hash collisions silently reassign replicas",
                        comment="Two virtual nodes that hash to the same value overwrite each other in `owners`, leaving a duplicate in `hashes` that points at the wrong node. With CRC32 and hundreds of replicas this happens in practice.",
                        confidence="medium",
                    ),
                    SampleFinding(
                        anchor="for j, candidate := range r.hashes {",
                        severity="info",
                        category="performance",
                        title="Removing a node scans the whole ring per replica",
                        comment="`Remove` is O(replicas × ring size). The slice is sorted, so `sort.Search` finds each hash directly.",
                        confidence="medium",
                    ),
                    SampleFinding(
                        anchor="func (r *Ring) Owner",
                        severity="warning",
                        category="missing-test",
                        title="No tests for distribution or wrap-around",
                        comment="The ring's two core properties — keys spread evenly, and keys above the highest hash wrap to the first node — aren't tested. The wrap-around case would have caught the panic above.",
                    ),
                ),
            ),
            SampleFile(filename="go.sum", skipped_size=(4, 0)),
        ),
    ),
    SampleReview(
        repo="payments-api",
        number=155,
        title="Currency conversion for multi-currency payouts",
        body="Payouts in a different currency from the charge are converted at the latest FX rate before transfer.",
        author="maya-chen",
        head_ref="feature/fx-payouts",
        days_ago=2,
        files=(
            SampleFile(
                filename="app/services/fx.py",
                status="added",
                after=FX_PY,
                summary="FX rate lookup and conversion. Rates are refetched per amount and every currency is rounded to cents.",
                findings=(
                    SampleFinding(
                        anchor="return [await convert(amount, base, quote) for amount in amounts]",
                        severity="warning",
                        category="performance",
                        title="Fetches the exchange rate once per amount",
                        comment="`convert_many` calls `get_rate` — a new HTTP client and request — for every amount, so a 1,000-line payout makes 1,000 identical rate requests. Fetch the rate once and convert in memory.",
                        suggested_fix='    if base == quote:\n        return amounts\n    rate = await get_rate(base, quote)\n    return [(amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for amount in amounts]',
                    ),
                    SampleFinding(
                        anchor='return converted.quantize(Decimal("0.01")',
                        severity="warning",
                        category="bug",
                        title="Rounds every currency to two decimal places",
                        comment="Not every currency has cents: JPY has no minor unit and BHD has three. Quantizing to `0.01` produces amounts the target currency can't represent.",
                    ),
                    SampleFinding(
                        anchor='return Decimal(str(response.json()["rates"][quote]))',
                        severity="warning",
                        category="bug",
                        title="Unsupported currencies raise a bare KeyError",
                        comment="A currency code missing from the rates response raises `KeyError`, which surfaces as a 500 from the payout endpoint instead of a clear validation error.",
                    ),
                    SampleFinding(
                        anchor="async def get_rate",
                        severity="warning",
                        category="missing-test",
                        title="No tests for conversion or rounding",
                        comment="Currency conversion is easy to get subtly wrong. Tests for same-currency passthrough, rounding and an unsupported code would lock the behaviour down.",
                        confidence="medium",
                    ),
                ),
            ),
            SampleFile(
                filename="app/routes/payouts.py",
                before=PAYOUTS_BEFORE,
                after=PAYOUTS_AFTER,
                summary="Payouts convert to the destination currency before transfer.",
                findings=(
                    SampleFinding(
                        anchor="Decimal(payout.amount)",
                        severity="critical",
                        category="bug",
                        title="`Decimal(float)` keeps binary float error",
                        comment="If `payout.amount` is a float, `Decimal(payout.amount)` preserves its binary representation — `Decimal(0.1)` is `0.1000000000000000055511151231257827…` — and the error can survive rounding. Build it from a string.",
                        suggested_fix="    amount = await convert(Decimal(str(payout.amount)), payout.currency, payout.destination.currency)",
                        confidence="medium",
                    ),
                ),
            ),
        ),
    ),
)
