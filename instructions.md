# SP LabLink deployment

This checkout runs the same LabLink campus equipment and scheduling workflows as the original project. Use **Vercel with PostgreSQL** for a standalone hosted demo or follow the [Google Cloud Run guide](implementation.md) for the container deployment. The PromptWars × Cynergy briefing requires a working Cloud Run link for top-10 eligibility. Use the Cloud Run guide if you are submitting to that event.

## 1. Publish this checkout to its own repository

Work from `C:/projects/SP-lablink`. Use a repository you control for this copy. Create an empty GitHub repository and substitute its clone URL below.

~~~powershell
Set-Location C:/projects/SP-lablink
git init -b main
git add .
git status --short
git commit -m "Initialize SP LabLink"
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
~~~

Use `git init` and `git remote add` only for a folder without an existing Git repository or remote. The staged list should contain source, lockfiles, tests and documentation. Keep local environments, credentials, installed dependencies and build output out of Git.

## 2. Create the Vercel project and database

1. In Vercel, import **your new SP LabLink repository**. Set the Root Directory to the repository root and the framework to **FastAPI**. Use the build settings from `vercel.json` and leave the Output Directory on its framework default. The build compiles Vite and includes `frontend/dist` with the Python app. FastAPI serves both the SPA routes and `/api` on the same origin.
2. Create a PostgreSQL database dedicated to SP LabLink. The [Neon integration](https://neon.com/docs/guides/vercel-managed-integration) is available in the Vercel Marketplace. Connect it to this Vercel project, then make sure a pooled connection URL is available as `DATABASE_URL`. If the integration uses a different variable name, add `DATABASE_URL` with its value. Use the provider's TLS connection URL, typically with `sslmode=require` already included.
3. Place the Vercel Function near your database region where possible. The application creates its `lablink_state` table on first startup, so the account in `DATABASE_URL` needs permission to create its table in the default schema. A transaction locks the shared demo state before changing a booking. Use a separate database or branch for Preview deployments if you enable them. A Preview should never share the Production demo data.

[Vercel FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi) · [Vercel Functions](https://vercel.com/docs/functions)

## 3. Configure environment variables

In **Vercel > Project > Settings > Environment Variables**, set these values for **Production** before deploying. Leave **Automatically expose System Environment Variables** enabled so the app detects its hosted environment.

| Name | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `STORAGE_BACKEND` | `postgres` |
| `DATABASE_URL` | The PostgreSQL connection URL. Mark as **Secret**. |
| `SESSION_SECRET` | A stable, unique random value. Mark as **Secret**. |
| `DEMO_MODE` | `true` |
| `SEED_DEMO_DATA` | `true` |

Generate one session value with the following command and paste it into the private Vercel settings form.

~~~powershell
py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
~~~

### Enable Gemini

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey). Use a project and key dedicated to the demo if possible. Check model availability and quotas in that account.
2. Add `AI_ENABLED=true`, `AI_PROVIDER=apikey`, `GEMINI_MODEL=gemini-3.5-flash`, and `GOOGLE_API_KEY` with the key value. Mark the key as **Secret**. The app uses it only in Python. A `VITE_` variable would be exposed to the browser.
3. For a trial without Gemini credentials, set `AI_ENABLED=false`. Booking and allocation still work, and suggestions are explicitly marked **Rules-based**. To demonstrate GenAI, enable Gemini and verify a live response before sharing the URL.

[Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key) · [Vercel environment variables](https://vercel.com/docs/environment-variables)

## 4. Deploy and verify

Deploy or redeploy from the Vercel project dashboard after the environment variables are set. Keep the public Production URL. Use a private browser window to verify visitors can open it. If the page requires a Vercel login, review **Deployment Protection** for the Production domain.

~~~powershell
$LablinkUrl = 'https://YOUR-PROJECT.vercel.app'
curl.exe --fail --silent --show-error "$LablinkUrl/api/healthz"
curl.exe --fail --silent --show-error "$LablinkUrl/api/readyz"
curl.exe --fail --silent --show-error -I "$LablinkUrl/discover"
~~~

Health should report `storage: postgres`; readiness should return `status: ready`. For a live AI check, continue as **Aarav Shetty**, ask for **Measure 2.4 GHz antenna signals**, and confirm the **AI-generated** badge. In DevTools > Network > `search`, the JSON should contain `"source":"ai"`. The health endpoint's `ai_enabled` field only confirms initialization.

Verify the shared workflow with separate browser sessions. Apply the seeded spectrum analyser allocation as **Dr. Meera Kulkarni**. Then sign in as **Aarav** to find the confirmed reservation under **Upcoming**, and as **Sneha Pai** to accept an offered slot. Sign in as **Ravi** to review analytics and restore the demo from **Manage > Reset demo data** after testing. That reset replaces shared synthetic data, so coordinate with anyone else using the demo.

## Troubleshooting and maintenance

| Symptom | Check |
| --- | --- |
| Home page renders HTML but JavaScript returns 404 | Confirm the root directory is the repository root, the Vite build ran, and the FastAPI build includes `frontend/dist/**`. |
| The API returns a startup error | Confirm all Production environment values were set before the latest deploy. Check the Python function log for the first error. |
| PostgreSQL permission or connection error | Check the database URL, TLS settings, database availability, and permission to create `lablink_state`. Keep the session secret and database URL private. |
| The search badge says Rules-based | Check `AI_ENABLED`, the API key, model availability and Gemini quota. Watch the Vercel function logs for the AI failure type. |
| Bookings differ across previews | Confirm which PostgreSQL database each deployment is using. Preview and Production are intentionally separate when configured with different connection URLs. |

The PostgreSQL adapter stores one transactional snapshot for this campus demo. Keep the hosted project limited to synthetic data. For a long-running multi-campus service, the storage model would need indexing and separate data partitions. When retiring the demo, remove its Production environment secrets and revoke its dedicated Gemini key.

For the optional native Google Cloud deployment, use the [Cloud Run and Vertex AI guide](implementation.md).
