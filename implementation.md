# Optional Cloud Run deployment with Vertex AI

Use this guide to deploy the SP LabLink container from your own checkout. The deployable unit is one Cloud Run service serving both the React frontend and the FastAPI API. The demo uses seeded data and Vertex AI Gemini through a Google-managed runtime identity. The briefing requires a working public Cloud Run deployment for top-10 eligibility.

## 1. Prepare your workstation and Google Cloud project

1. Install the [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install), Git, and Python 3.12. Use Windows PowerShell or PowerShell 7 for the commands below. Docker Desktop is optional for local verification. Cloud Build can build the image remotely.
2. Open the [Google Cloud Console](https://console.cloud.google.com/) and select or create a project you are authorized to use. Link billing, copy the **project ID**, and optionally create a budget alert under **Billing > Budgets & alerts**. A budget alert sends notifications. Usage can continue after the alert.
3. Open the SP LabLink checkout. Run the commands below from its root.

~~~powershell
Set-Location C:/projects/SP-lablink
gcloud --version
py -3.12 --version
~~~

If you published SP LabLink separately, confirm the local version matches the GitHub commit you intend to deploy.

## 2. Sign in and enable the APIs

Set `$LablinkProject` to your real project ID. Use the same PowerShell session for the rest of the guide.

~~~powershell
$LablinkProject = 'YOUR_GCP_PROJECT_ID'
$LablinkRegion = 'asia-south1'
$LablinkService = 'lablink'
$LablinkModel = 'gemini-3.5-flash'
$LablinkSecret = 'lablink-session-secret'
$LablinkRuntime = "lablink-run@$LablinkProject.iam.gserviceaccount.com"
$LablinkBuilder = "lablink-build@$LablinkProject.iam.gserviceaccount.com"

gcloud auth login
gcloud projects describe $LablinkProject --format='value(projectId)'
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com secretmanager.googleapis.com --project=$LablinkProject
~~~

The Cloud Run service region and the Gemini endpoint are separate settings. This guide uses Mumbai for Cloud Run and `global` for Gemini 3.5 Flash. If `services enable` returns a permission error, a project administrator can enable the APIs. [Cloud Run source deployment](https://docs.cloud.google.com/run/docs/deploying-source-code) · [Gemini 3.5 Flash availability](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash)

## 3. Create the build and runtime identities

Run these commands once for a fresh project. If an identity already exists, reuse it and verify its grants. A project administrator can run the IAM commands if your account lacks permission.

~~~powershell
gcloud iam service-accounts create lablink-build --display-name='LabLink source build' --project=$LablinkProject
gcloud iam service-accounts create lablink-run --display-name='LabLink Cloud Run runtime' --project=$LablinkProject

gcloud projects add-iam-policy-binding $LablinkProject --member="serviceAccount:$LablinkBuilder" --role=roles/run.builder
gcloud projects add-iam-policy-binding $LablinkProject --member="serviceAccount:$LablinkRuntime" --role=roles/aiplatform.user
~~~

If the deployer is a separate account, have the project administrator grant that deployer `roles/run.sourceDeveloper` and `roles/serviceusage.serviceUsageConsumer` on the project and `roles/iam.serviceAccountUser` on both LabLink service accounts. The administrator may also need to enable public invocation after deployment. The runtime uses Application Default Credentials from its attached service account. There is no service-account key file or Gemini API key to create. [Cloud Build identity](https://docs.cloud.google.com/run/docs/configuring/services/build-service-account) · [Application Default Credentials](https://docs.cloud.google.com/docs/authentication/application-default-credentials)

## 4. Create the session signing secret

Run this block once if `lablink-session-secret` does not exist. It generates the value in a temporary file outside the repository and removes the file when the command finishes.

~~~powershell
$LablinkSecretFile = [IO.Path]::GetTempFileName()
try {
    $LablinkSecretValue = py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
    if ($LASTEXITCODE -ne 0 -or $LablinkSecretValue.Length -lt 32) { throw 'Could not generate session secret' }
    [IO.File]::WriteAllText($LablinkSecretFile, $LablinkSecretValue, [Text.Encoding]::ASCII)
    gcloud secrets create $LablinkSecret --replication-policy=automatic --data-file=$LablinkSecretFile --project=$LablinkProject
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Secret Manager secret' }
} finally {
    Remove-Item -LiteralPath $LablinkSecretFile -ErrorAction SilentlyContinue
    Remove-Variable LablinkSecretValue -ErrorAction SilentlyContinue
}
~~~

Grant access to the runtime on this secret only. Use the enabled version number printed by the last command. For a new secret it will normally be `1`.

~~~powershell
gcloud secrets add-iam-policy-binding $LablinkSecret --member="serviceAccount:$LablinkRuntime" --role=roles/secretmanager.secretAccessor --project=$LablinkProject
gcloud secrets versions list $LablinkSecret --filter='state=ENABLED' --project=$LablinkProject
$LablinkSecretVersion = '1'
~~~

A numbered version keeps the deployed revision tied to the same signing key. Replacing that value invalidates existing sessions. [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets)

## 5. Deploy the source to Cloud Run

From the repository root, review what will be uploaded. The manifest should contain the Dockerfile, application code, and dependency and build files. The briefing PDF, local environments, dependencies, build output, credentials, and Git history should be absent.

~~~powershell
gcloud meta list-files-for-upload
~~~

Deploy the prepared source. Wait for the build and the new revision to finish. If the CLI asks to create the regional Artifact Registry repository for source deployments, confirm that it is in your project and region.

~~~powershell
gcloud run deploy $LablinkService `
  --project=$LablinkProject --region=$LablinkRegion --source=. `
  --build-service-account="projects/$LablinkProject/serviceAccounts/$LablinkBuilder" `
  --service-account=$LablinkRuntime --ingress=all --no-invoker-iam-check `
  --cpu=1 --memory=512Mi --concurrency=20 --port=8080 --timeout=60 --cpu-boost `
  --min=1 --max=1 `
  --startup-probe='httpGet.path=/api/readyz,httpGet.port=8080,periodSeconds=5,timeoutSeconds=3,failureThreshold=12' `
  --set-env-vars="APP_ENV=production,STORAGE_BACKEND=memory,GCP_PROJECT=$LablinkProject,AI_ENABLED=true,AI_PROVIDER=vertex,GEMINI_MODEL=$LablinkModel,GEMINI_LOCATION=global,DEMO_MODE=true,SEED_DEMO_DATA=true" `
  --set-secrets="SESSION_SECRET=${LablinkSecret}:${LablinkSecretVersion}"
if ($LASTEXITCODE -ne 0) { throw 'Cloud Run deployment failed. Read the build or revision error before retrying.' }

$LablinkUrl = (gcloud run services describe $LablinkService --project=$LablinkProject --region=$LablinkRegion --format='value(status.url)').Trim()
$LablinkUrl
~~~

The service-level minimum keeps one instance warm during judging and can incur charges. The maximum of one limits independent copies of in-memory demo state. Instance replacement or revision changes can reseed the shared demo. Keep all traffic on the tested revision and use demo data only. [Public access](https://docs.cloud.google.com/run/docs/authenticating/public) · [Scaling](https://docs.cloud.google.com/run/docs/configuring/min-instances) · [Health checks](https://docs.cloud.google.com/run/docs/configuring/healthchecks)

## 6. Verify the deployment and Vertex AI

### Public readiness

Run these from a terminal without adding a Google identity token. The service must work for an evaluator who has no Google Cloud access.

~~~powershell
curl.exe --fail --silent --show-error "$LablinkUrl/api/healthz"
curl.exe --fail --silent --show-error "$LablinkUrl/api/readyz"
curl.exe --fail --silent --show-error --head "$LablinkUrl/discover"
curl.exe --silent --show-error --output NUL --write-out '%{http_code}' "$LablinkUrl/api/docs"
~~~

Expect `status: ok`, `storage: memory`, `ai_enabled: true`, and `model: gemini-3.5-flash` from health, `status: ready` from readiness, HTTP 200 on the deep link, and HTTP 404 on API docs.

### Verify an actual Gemini response

A healthy API with `ai_enabled: true` means the Gemini client initialized. Verify inference separately, with a temporary PowerShell web session that holds the app's secure cookie. These commands use a seeded student account and a demonstration prompt.

~~~powershell
$LablinkHeaders = @{ 'X-Requested-With' = 'LabLink' }
Invoke-RestMethod -Method Post -Uri "$LablinkUrl/api/auth/demo" -Headers $LablinkHeaders -ContentType 'application/json' -Body (@{ persona_id = 'u-aarav' } | ConvertTo-Json -Compress) -SessionVariable LablinkSession | Out-Null
$LablinkSearch = Invoke-RestMethod -Method Post -Uri "$LablinkUrl/api/ai/search" -Headers $LablinkHeaders -ContentType 'application/json' -WebSession $LablinkSession -Body (@{ query = 'measure 2.4 GHz antenna signals' } | ConvertTo-Json -Compress)
$LablinkSearch | Select-Object source, interpreted
$LablinkSearch.results | Select-Object -First 3 equipment_id, match, reason
if ($LablinkSearch.source -ne 'ai') { throw 'Gemini did not return a validated AI response. Check the Cloud Run logs.' }
~~~

The response should include `source: ai` and relevant catalogue equipment. In Chrome you can also check the **AI-generated** badge or the `search` response in DevTools > Network. A **Rules-based** badge means the fallback ran.

### Verify the judge's browser flow

1. Open the service URL in an incognito window. Sign in as **Aarav Shetty**, run the antenna search, and open the suggested analyser. Try a separate instant-booking item to check the calendar and booking confirmation.
2. Switch to **Dr. Meera Kulkarni**. Open **Conflicts**, select the spectrum analyser, choose **Recommend fair allocation**, and then **Apply allocation > Apply and notify**. Verify the ranking, score breakdown, and confirmed or alternative outcomes.
3. Switch to **Aarav** and check **My bookings > Upcoming** for the winning reservation. Switch to **Sneha Pai**, open **My bookings > Needs action**, and confirm an offered alternative.
4. Switch to **Ravi** and open **Analytics**. Confirm that charts and their table views load and that **Generate insights** returns an AI-generated response. Reload a deep link while signed in.
5. Before handing over, restore the seeded scenario using **Ravi > Manage > Reset demo data**. This replaces shared demo activity. Use it only before judging and after other testers have finished. Confirm the spectrum analyser conflict is open again, then leave it intact.

## 7. Submit to PromptWars

- Open your published repository?s **Actions** tab and verify CI for the same commit used for deployment. The backend and frontend jobs attach test reports. The container job verifies the production image.
- Submit your SP LabLink repository?s public clone URL ending in `.git`. Verify in a signed-out browser that it is public. `git ls-remote --heads origin` should show one branch, `main`. The event requires the repo to be under 10 MB.
- Submit the exact `https://...run.app` address from Step 5 as the deployed project URL. Optionally link it from the README after verifying it.
- Publish a LinkedIn project post with public visibility. Include what LabLink solves, what you built, the live demo, and the GitHub link. Copy the post's permalink and open it signed out to check visibility.
- Paste a brief description in the submission form. You can use the text below.
- If you are entering PromptWars, sign in to the event platform with the email used to register. Check all links before using attempt one. The briefing permits two scored attempts and the latest score counts. Use the technical retry only if the platform reports a technical or connectivity failure.

> LabLink helps college students find and book specialist equipment across departments. Students can request project access, faculty can approve it and resolve competing bookings using an explainable priority score, and administrators can track utilization. Vertex AI Gemini helps interpret equipment needs and explain outcomes. The booking service checks availability and eligibility before confirming reservations.

## Troubleshooting and after judging

| Symptom | What to check |
| --- | --- |
| Build fails before a revision is created | Open Cloud Build History and read the first failing step. For build IAM errors, check the selected build identity has `roles/run.builder` and the deployer can act as it. IAM grants can take a few minutes to propagate. |
| Service URL returns 401 or 403 while signed out | Check **Cloud Run > lablink > Security > Allow public access** and ingress. If an organization policy blocks public access, ask the project administrator for an eligible project. |
| Revision fails to start | Check Cloud Run logs. Verify port 8080, readiness path, the enabled secret version, and the runtime identity's access to that secret. |
| Health reports `ai_enabled: false` | Check `GCP_PROJECT`, `AI_ENABLED`, and runtime identity initialization in logs. |
| Health is OK but search returns `fallback` | Check Vertex AI API enablement, billing, `roles/aiplatform.user` on the runtime account, Gemini model access and the `global` endpoint. For a 429, check Vertex AI quota and retry briefly after the limit clears. |
| A deep link serves a 404 | Check that the Cloud Build log used the root Dockerfile and copied `frontend/dist` into `app/static`. |
| The seeded conflict is missing | The previous browser run may have resolved it. See the reset step above before the evaluation window. |

~~~powershell
gcloud run services logs read $LablinkService --project=$LablinkProject --region=$LablinkRegion --limit=80
gcloud run revisions list --service=$LablinkService --project=$LablinkProject --region=$LablinkRegion
~~~

Once the organizers have finished reviewing the live URL, you can let the service scale to zero when idle. Confirm costs in Billing. Container images stored in Artifact Registry can still accrue storage charges.

~~~powershell
gcloud run services update $LablinkService --project=$LablinkProject --region=$LablinkRegion --min=0
~~~
