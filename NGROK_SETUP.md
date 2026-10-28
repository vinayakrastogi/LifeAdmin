# LifeAdmin at a fixed internet address

The assigned endpoint is:

```text
https://polygon-coastal-glazing.ngrok-free.dev
```

The API and its data still run on the computer hosting LifeAdmin. ngrok forwards
HTTPS requests to that computer's local API on port 8001. The same assigned
domain can be used after changing Wi-Fi or moving the service to another device.

## First-time setup on your friend's computer

Pull the updated LifeAdmin repository. Install Python 3.11+ and the ngrok CLI
from https://ngrok.com/download. On macOS, `brew install ngrok` also works.

In LifeAdmin:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell activation: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For a fresh checkout, copy `.env.example` to `.env`. Fill in:

```dotenv
LIFEADMIN_API_KEY=<same-service-key-used-by-edT>
LIFEADMIN_SOURCE_APP=pylearn
NGROK_AUTHTOKEN=<authtoken-from-the-domain-owners-ngrok-account>
NGROK_DOMAIN=polygon-coastal-glazing.ngrok-free.dev
```

The ngrok authtoken authenticates the tunnel; the LifeAdmin API key authenticates
edT's requests. Both are local credentials. Git ignores `.env`, database files,
and backups. The example contains only the public domain and empty placeholders.
Use the same LifeAdmin API key on both computers; changing the tunnel host does
not require changing this shared key.

With `LIFEADMIN_SEED_DEMO_USERS=true`, normal API/UI startup creates or updates
these presentation accounts automatically:

| Account | Email | Password |
|---|---|---|
| Student | `demostudent@example.com` | `demostudent` |
| Faculty | `demofaculty@example.com` | `demofaculty` |

The original demo learner is renamed to the student account while preserving its
notes. Other users keep their accounts. Use the same email in PyLearn and
LifeAdmin to see your own lesson notes. No database reset is needed to add these
accounts. See `API.md` for an optional explicit reset with backup.

## Normal startup

Activate the environment and run:

```bash
python scripts/run_api.py
```

The launcher reads this project's `.env`, starts Uvicorn, waits for the API,
starts ngrok with the assigned domain, and checks the public health endpoint.
It prints the public URL once ready. Ctrl+C stops both child processes. If the
API or tunnel exits, the remaining process is stopped too. The authtoken is
loaded through a private temporary ngrok configuration and omitted from command
arguments and redacted from launcher output.

The optional Streamlit interface is still started separately:

```bash
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Open http://localhost:8501 and log in. The tunnel exposes the API on port 8001;
the Streamlit interface stays local to the hosting computer.

To run only the local API without opening a tunnel:

```bash
python scripts/run_api.py --local-only
```

## edT configuration

In edT's root `.env`:

```dotenv
LIFEADMIN_API_URL=https://polygon-coastal-glazing.ngrok-free.dev
LIFEADMIN_DOCKER_API_URL=https://polygon-coastal-glazing.ngrok-free.dev
LIFEADMIN_API_KEY=<same-service-key-as-LifeAdmin>
```

The two URL settings cover manual and Docker startup. From edT, restart its
stack after environment changes:

```bash
docker compose up -d --build
```

edT's backend calls the public HTTPS URL and includes the service key. It also
sends the ngrok browser-warning bypass header, so calls receive API responses.
The browser and edT do not need the ngrok authtoken or a separate ngrok account.

## Move hosting from your computer to your friend's

1. Stop `scripts/run_api.py` on the old host using Ctrl+C.
2. On the new host, configure the local `.env` with the same account's ngrok
   authtoken, assigned domain, and LifeAdmin API key.
3. If you need existing users and notes, copy the stopped LifeAdmin database
   privately to the new host. Git does not transfer it. Copy `data/uploads/`
   too if you need existing uploaded documents. A fresh reset creates an empty
   database with the two demo accounts.
4. Start `python scripts/run_api.py` on the new host.
5. Check `/health` at the fixed URL and save a lesson note from edT.

edT's URL stays the same. Keep the new host online with its API and tunnel
running. Only one host should serve this endpoint for this setup at a time.

## Useful addresses

| Purpose | Address |
|---|---|
| Public health | https://polygon-coastal-glazing.ngrok-free.dev/health |
| Public interactive API docs | https://polygon-coastal-glazing.ngrok-free.dev/docs |
| OpenAPI schema | https://polygon-coastal-glazing.ngrok-free.dev/openapi.json |
| Hosting computer's UI | http://localhost:8501 |

If ngrok reports the endpoint is already online, stop its old host's tunnel
first. For invalid credentials or domain errors, verify the authtoken and domain
belong to the same account. If no `ngrok` command is found, install its CLI and
open a new terminal. Keep the account within its free-plan usage limits.

Reference: https://ngrok.com/docs/pricing-limits/free-plan-limits
