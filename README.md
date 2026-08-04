# Community Board Dashboard

## Run locally

```bash
export FLASK_APP=flask_app.py
export API_KEY=<your-api-key>
cd app
flask run --reload
```

Then open http://127.0.0.1:5000/webresults

---

## AWS Infrastructure

### Overview

- **Lambda**: `CBFunction` — Python 3.8, handles all API routes. `deploy_lambda.sh` bundles `app/requirements.txt` dependencies directly into the deploy zip (see below) — no separate Lambda layer.
- **API Gateway**: HTTP API (v2), catch-all `$default` route → Lambda, stage named `default`
- **Custom domain**: `internal.mcb7.org` → API Gateway, certificate managed in ACM
- **DNS**: Route 53, ALIAS record for `internal.mcb7.org`

### Lambda environment variables

| Variable | Description |
|---|---|
| `API_KEY` | Shared secret checked via `x-api-key` header on all authenticated endpoints |
| `TWILIO_API_KEY` | Shared secret embedded in the Twilio webhook URL (`auth=` param) |

### Deployment scripts

| Script | Purpose |
|---|---|
| `./deploy_lambda.sh` | Install deps + update Lambda function code (default) — only deploys committed (`git archive`) files, commit first |
| `./deploy_lambda.sh --new` | Create Lambda function for the first time |
| `./deploy_api_gateway.sh` | Create the HTTP API Gateway (first-time setup) |
| `./deploy_custom_domain.sh` | Request ACM cert, create custom domain, wire up Route 53 (first-time setup) |

### First-time setup order

1. `./deploy_lambda.sh --new`
2. `./deploy_api_gateway.sh`
3. `./deploy_custom_domain.sh`
4. Set environment variables on the Lambda:
   ```bash
   aws lambda update-function-configuration \
     --profile mcb7 \
     --region us-east-1 \
     --function-name CBFunction \
     --environment "Variables={API_KEY=<value>,TWILIO_API_KEY=<value>}"
   ```

---

## API endpoints

All endpoints are available at `https://internal.mcb7.org/`.

Authenticated endpoints require headers:
- `x-api-key: <API_KEY>`
- `x-community-board: <board_number>`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | No | Serve the dashboard HTML page |
| GET | `/members` | Yes | Get member list |
| POST | `/members` | Yes | Set member list |
| POST | `/startvoting` | Yes | Start a vote |
| POST | `/stopvoting` | Yes | Stop a vote |
| GET | `/results` | Yes | Get current vote results |
| GET | `/isvotingstarted` | Yes | Check if voting is active |
| POST | `/exportvotes` | Yes | Export votes for a date |
| POST | `/manualentry` | Yes | Manually submit a vote |
| POST | `/incomingtext` | URL param | Twilio SMS webhook |

---

## Twilio

Webhook URL to configure in the Twilio console:

```
https://internal.mcb7.org/incomingtext?auth=<TWILIO_API_KEY>&cb=<community_board_number>
```

The `auth` param must match the `TWILIO_API_KEY` environment variable on the Lambda.

---

## Upload members

```bash
python3 uploadmembers.py
```

---

## Testing concurrent votes

`test_concurrent_votes.sh` sends votes from multiple phone numbers simultaneously to exercise the `/incomingtext` endpoint under load.

Phone numbers are read from a local `test_numbers.txt` file (one number per line) that is gitignored to keep member data out of the repo.

```
+12125551234
+12125555678
...
```

Run the test:

```bash
./test_concurrent_votes.sh
```

Or pass a custom numbers file:

```bash
./test_concurrent_votes.sh path/to/other_numbers.txt
```
