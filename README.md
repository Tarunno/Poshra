<p align="center">
  <img src="docs/brand/poshra-mark.svg" alt="" width="88" height="88">
</p>

<h1 align="center">Poshra</h1>

<p align="center">
  <strong>Crafts from Bangladesh, sold the way they deserve.</strong><br>
  <em>পসরা — the spread of goods a trader lays out at the fair.</em>
</p>

<p align="center">
  <img src="docs/assets/hero.png" alt="Poshra on four screens: the shop with craft filters on a monitor, an artisan speaking a listing into being on a laptop, the mobile storefront on a phone, and Pahara explaining what the cluster has been doing on a tablet" width="960">
</p>

<p align="center">
  <sub>
    Next.js · Django · Go · Kong · Kafka · gRPC · Postgres · Kubernetes ·
    OpenTelemetry · Gemini&nbsp;/&nbsp;Claude
  </sub>
</p>

<p align="center">
  <img src="docs/assets/cover-pahara.png" alt="Pahara, the watch: an agent that reads the cluster's traces, logs and metrics, answering a question about slowness and listing the five queries it ran" width="960">
</p>

---

## What it is

A marketplace that connects Bangladeshi artisans to buyers abroad and keeps the maker
attached to the work: every piece says who made it and which district it came from.

**Buyers** ask in plain language — *"a wedding gift under ৳8,000"*, *"something handwoven
from Sylhet"* — and get real pieces back, not keyword soup. **Artisans** photograph a piece
and say what it is out loud, in Bangla, and get a listing in English to correct: title,
description, materials and a price judged against comparable work already in the shop.
**Agents** get the storefront as a set of described tools; the model can fill a cart but
never spend money — buying ends with a human on the checkout page.

Nothing the model writes is published. It fills a form the artisan corrects, for the same
reason it can total a cart but not pay for it.

**Whoever keeps the shop** sees all of it: every artisan's listings, what sold, and a note
against a piece when something needs changing — archived with a reason rather than deleted,
and the artisan can answer it.

<p align="center">
  <img src="docs/assets/cover-product.png" alt="Poshra on four screens: the oversight board for the whole marketplace on a monitor and again on a phone, the storefront on a laptop, and the listing editor in a browser window" width="960">
</p>

---

## Built like production

Nine services behind an API gateway on a three-node Kubernetes cluster, deployed by GitOps,
with all three observability signals joined up.

<p align="center">
  <img src="docs/assets/cover-observability.png" alt="A Grafana trace from Kong through checkout into the Kafka consumers, the Hubble service map, a rate-errors-duration dashboard, and Argo CD with three applications synced" width="960">
</p>

One trace runs from the gateway to the database **and across Kafka into two languages**: the
order's trace context is written into the outbox row, resumed by the relay, and picked up
independently by a Go consumer and a Python one. The publish span's duration *is* outbox
latency; the gap before a consume span *is* consumer lag. Logs are structured JSON parsed on
the way into Loki and carry that trace id; RED metrics are derived from the spans themselves.
Hubble shows every flow Cilium allows or drops, so a NetworkPolicy is visible rather than
assumed, and Argo CD makes git the only way the cluster changes — migrations run as a PreSync
hook before any pod starts.

<p align="center">
  <img src="docs/assets/cover-cluster.png" alt="How the cluster hangs together: a request through MetalLB and Kong to nine services, an order travelling from checkout's outbox through Kafka into two consumers, and every service's telemetry reaching Tempo, Loki and Prometheus — on three nodes, deployed by Argo CD" width="960">
</p>
