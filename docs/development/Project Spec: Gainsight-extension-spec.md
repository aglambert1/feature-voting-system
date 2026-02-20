Project Spec: Gainsight AI-Feedback Connector

1. Objective
   Develop a Node.js/TypeScript connector that bridges Gainsight data with an AI processing layer. The connector will:

Poll for new customer feedback submissions (Timeline or Custom Objects).

Export historical data for thematic clustering/duplicate detection.

Push AI-generated summaries and responses back into Gainsight.

2. Infrastructure & Auth
   Gainsight Edition: Gainsight NXT (CS) or Gainsight PX.

Authentication: Header-based accesskey.

Base URL: https://{tenant-prefix}.gainsightcloud.com/v1/

Environment: Node.js (running on external compute).

3. Core Implementation Details
   A. Polling for New Submissions (Real-time Analysis)

Instead of the Rules Engine, use the Data Management Read API to poll specific objects (e.g., Product_Request\_\_gc or Timeline).

Endpoint: POST /v1/data/objects/{objectName}\_\_gc/read

Logic: Store a last_polled_at timestamp. Query for records where CreatedDate > last_polled_at.

Filter Syntax (JSON Body):

JSON
{
"select": ["Gsid", "Subject__gc", "Description__gc", "CreatedDate"],
"where": {
"conditions": [
{
"fieldName": "CreatedDate",
"operator": "greater than",
"value": ["2023-10-27T10:00:00.000Z"]
}
]
},
"limit": 50
}
B. Bulk Extraction (Thematic Analysis)

To identify themes across thousands of records, use the Gainsight Bulk API (V3) to avoid hitting sync rate limits.

Step 1 (Submit): POST /v3/exports/data/bulk/{objectName}

Step 2 (Status): GET /v3/exports/data/bulk/{jobId}/status

Step 3 (Fetch): Download CSV/JSON chunks once the job is complete.

Usage: Feed the extracted Description fields into an LLM for clustering and duplicate identification.

C. Programmatic Insertion (Closing the Loop)

Once your AI generates a recommendation or response, write it back to Gainsight so the CS/Product team sees it.

Strategy 1: Timeline Post (Best for visibility)

Endpoint: POST /v1/ant/es/activity

Payload: Include Subject, Notes (your AI analysis), and the ExternalId of the original request.

Strategy 2: Custom Object Update

Endpoint: POST /v1/data/objects/{objectName}\_\_gc

Payload: Update the AI_Summary\_\_gc field on the specific record ID.

4. Developer Workflow for Claude Code
   To initialize this project, point Claude Code to the following file structure:

config.ts: Manage environment variables (GS_ACCESS_KEY, GS_DOMAIN, POLL_INTERVAL).

gsClient.ts: A wrapper for axios to handle the accesskey header and retry logic for the 100 calls/min rate limit.

poller.ts: The main loop that fetches data, triggers your AI logic, and tracks the cursor (timestamp).

analyzer.ts: Integration point for your LLM logic (e.g., OpenAI/Anthropic) to handle the data fetched.

5. Solo Dev Prototyping Options
   If you do not have an Enterprise Sandbox:

Gainsight PX Free Trial: Highly recommended for solo devs. You can create "Custom Events" to simulate product requests and use the PX REST API (api.aptrinsic.com) which is very developer-friendly.

The "Custom Object" Mock: If building for a client who has Gainsight, ask them to create one Low Volume Custom Object for you. This allows you to test the full CRUD lifecycle without touching their sensitive standard data.

6. Constraints & Limits
   Rate Limit: 100 calls/minute (Synchronous REST). For polling, use an interval of 2–5 minutes to stay safely within limits.

Pagination: Results are capped at 50 per call for custom objects; use offset for subsequent pages.
