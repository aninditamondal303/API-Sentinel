# Deploying API Sentinel to a free public server

This guide puts the complete stack (frontend, backend, analyzer, PostgreSQL) on one
**Oracle Cloud Always Free** Ampere A1 virtual machine behind **Caddy**, which serves a public
**HTTPS** URL with an automatically renewed **Let's Encrypt** certificate on a free
**DuckDNS** subdomain. Nothing here is paid.

The local development setup is unchanged: production adds one override file
(`infrastructure/docker-compose.prod.yml`) and a `Caddyfile`; the base `docker-compose.yml`
is used as-is.

```
Internet ──443/80──▶ Caddy (TLS, HSTS) ──▶ nginx frontend ──/api, /actuator/health──▶ Spring Boot backend
                                                                              ├──▶ Python analyzer (internal only)
                                                                              └──▶ PostgreSQL (internal only, volume pgdata)
```

Only ports 80 and 443 are published. PostgreSQL (5432), the analyzer (8081) and the backend
(8080) are reachable solely on the internal Docker network. The local-only host ports of the
base file (127.0.0.1:8080 and :3000) are removed by the override.

## Why Oracle Cloud Always Free

| Option | Fits the full stack? | Catch |
|---|---|---|
| **Oracle Always Free, Ampere A1** | Yes: 2 OCPU / 12 GB RAM (since 15 June 2026), 200 GB block storage, persistent disks | Card + phone verification at sign-up; A1 capacity can be temporarily unavailable; idle instances can be reclaimed |
| Oracle Always Free, E2.1.Micro | No: 1 GB RAM is too small for JVM + PostgreSQL + Python + nginx | — |
| Render free | Partly: separate 512 MB services | Spins down after 15 min idle (~1 min cold start); free PostgreSQL expires after 30 days |
| Google Cloud e2-micro | No: 1 GB RAM | Card required, US regions only |

## Part 1 — Steps only you can do (accounts and console)

1. **Create the Oracle Cloud account** at <https://www.oracle.com/cloud/free/>.
   Oracle asks for an e-mail address, a mobile number and a credit card or a debit card that
   works like a credit card (not prepaid, virtual or PIN debit). The card is for identity
   verification; it is not charged unless you upgrade.
   Choose the **home region** carefully (nearest to you): Always Free compute exists only there
   and it cannot be changed later. Do **not** upgrade to Pay As You Go.

2. **Create the VM**: Console → Compute → Instances → *Create instance*.
   * Image: **Canonical Ubuntu 24.04** (the aarch64 build is picked automatically for Ampere).
   * Shape: *Change shape* → Ampere → **VM.Standard.A1.Flex**, **2 OCPUs, 12 GB** memory. Check
     that the *Always Free-eligible* label is shown. Do not exceed 2 OCPU / 12 GB in total.
   * Networking: create a new VCN with a **public subnet** and **assign a public IPv4 address**.
   * SSH keys: *Generate a key pair for me* and **download the private key** (keep it safe;
     never commit it), or paste your own public key.
   * Boot volume: default size is fine.
   If you see "Out of capacity", try another availability domain or retry later; this is
   Oracle-side capacity, not a configuration error.

3. **Open ports 80 and 443 in the cloud firewall**: Networking → Virtual cloud networks → your
   VCN → Subnets → the public subnet → Security → *Default Security List* → *Add Ingress Rules*:
   * Source CIDR `0.0.0.0/0`, IP protocol TCP, destination port `80`
   * Source CIDR `0.0.0.0/0`, IP protocol TCP, destination port `443`
   * (optional, HTTP/3) Source CIDR `0.0.0.0/0`, IP protocol UDP, destination port `443`
   Do **not** add rules for 5432, 8080 or 8081.

4. **Get the free subdomain**: sign in at <https://www.duckdns.org> (GitHub, Google, …), add a
   subdomain, e.g. `apisentinel-yourname`, and set its IP to the VM's public IPv4 address.
   Your URL will be `https://apisentinel-yourname.duckdns.org`.

## Part 2 — On the server (copy-paste)

Connect from Windows PowerShell (OpenSSH is built into Windows):

```powershell
ssh -i C:\path\to\your-private-key.key ubuntu@<VM_PUBLIC_IP>
```

Then on the VM:

```bash
git clone https://github.com/aninditamondal303/API-Sentinel.git
cd API-Sentinel
bash scripts/deploy/server-setup.sh          # Docker from download.docker.com + host firewall 80/443
exit                                          # log out so the docker group applies, then ssh in again
cd API-Sentinel
bash scripts/deploy/deploy.sh apisentinel-yourname.duckdns.org you@example.com
bash scripts/deploy/verify.sh --restart       # infrastructure + end-to-end + persistence checks
```

`deploy.sh` creates `.env` on the server with freshly generated random secrets (mode 600,
git-ignored, never printed) and keeps them on every later run. The e-mail address is only given
to Let's Encrypt for certificate expiry notices.

The first build on the VM takes several minutes (Maven, npm and pip downloads, ARM64 images).

## Updating after a code change

```bash
cd ~/API-Sentinel
git pull
bash scripts/deploy/deploy.sh apisentinel-yourname.duckdns.org you@example.com
bash scripts/deploy/verify.sh
```

Data lives in the `apisentinel_pgdata` Docker volume and survives restarts, rebuilds and
redeployments. Certificates live in `apisentinel_caddy_data`. **Never** run
`docker compose down -v` or `docker volume rm` on the server: that deletes the database.

## Backups

```bash
bash scripts/deploy/backup-db.sh      # gzip'd pg_dump to ~/apisentinel-backups (mode 600, keeps 14)
```

## What verify.sh checks

* postgres, analyzer, backend and frontend containers are healthy; Caddy is running
* no host port is published except Caddy's 80/443; nothing listens on 5432, 8081, 8080, 3000
* `https://<domain>/` returns 200 with a valid certificate; HTTP redirects to HTTPS
* HSTS and Content-Security-Policy headers are present
* `/actuator/health` is `UP`; `/actuator`, `/actuator/env`, `/actuator/beans` return 404
* the API rejects unauthenticated requests; SPA deep links work
* `smoke_test.py`: register → login → create project → upload two specs → compatibility scan →
  findings → security scan → report → contract-test ZIP → dashboard → cross-user isolation
* with `--restart`: every container is restarted and the earlier account, project and findings
  are read back

## Known limitations of the free deployment

* **Single VM, no redundancy.** If Oracle stops the VM, the site is down until it is started.
* **Idle reclamation.** Oracle may stop Always Free instances it considers idle over 7 days
  (low CPU, network and — for A1 — memory utilisation). A stopped instance can be started again
  from the console; data on the boot volume is kept.
* **Public registration is open.** Anyone with the URL can create an account. There is no
  e-mail verification or rate limiting on sign-up.
* **DuckDNS** is a free community service; if it is down, the name does not resolve.
* The backend builds `Location` headers with `http://` because it does not trust forwarded
  headers; the web UI does not use them.

---

# Alternative: Render + Neon (no credit card)

`render.yaml` (repository root) is a Render Blueprint that runs the same application on free
plans that do not ask for a card:

| Part | Where | Notes |
|---|---|---|
| React frontend | Render static site `api-sentinel-app` | Never sleeps. Rewrites `/api/*` and `/actuator/health` to the backend, so the browser sees one origin. Same security headers as nginx. |
| Backend + analyzer | Render free web service `api-sentinel-api` (`deploy/render/Dockerfile`) | One container: the analyzer listens on `127.0.0.1:8081` only (Render free services cannot receive private traffic, so a separate analyzer would have to be public). 512 MB RAM, JVM capped accordingly. |
| PostgreSQL | Neon free plan | Permanent, no card. Connection string pasted into `DATABASE_URL` once, in the Render dashboard. Idle connections are closed so Neon can scale to zero. |

The JWT key and the internal token are generated by Render (`generateValue`) and never appear in
the repository. `.github/workflows/keep-awake.yml` pings the backend every 10 minutes so it
does not sleep (one always-on service ≈ 730 of the 750 free instance hours a month).

## Steps

1. **Neon**: sign up at <https://neon.com> (Continue with GitHub), create a project in region
   **AWS Asia Pacific (Singapore)**, and copy the connection string
   (`postgresql://…?sslmode=require…`).
2. **Render**: sign up at <https://render.com> (Continue with GitHub), then
   *New → Blueprint*, select this repository, and paste the Neon connection string into
   `DATABASE_URL` when asked. Click *Apply*.
3. Wait for both services to build (first backend build: several minutes). The site is at
   `https://api-sentinel-app.onrender.com` (Render adds a suffix if the name is taken; then
   update the two rewrite destinations in `render.yaml` and the URL in the keep-awake workflow).

## Limitations

* Free Render instances have 0.1 CPU: the first backend start takes minutes, and scans are
  slower than locally. If the keep-awake ping is late, a visitor may wait about a minute.
* The backend is also reachable directly at its own `onrender.com` URL (same API, same
  authentication). The analyzer and the database are not publicly reachable.
* Render may suspend free services for unusually high traffic; Neon free has 100 compute hours
  and 1 GB storage per month.
