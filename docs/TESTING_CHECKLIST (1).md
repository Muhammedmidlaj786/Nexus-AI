# Nexus AI — Manual Test Checklist

Use synthetic documents and demo accounts only. Record the actual result of each run.

| ID | Test | Expected result | Result |
|---|---|---|---|
| T01 | Upload one PDF and click Process | Document is processed and indexed | Pass/Fail |
| T02 | Upload multiple PDFs | Each document is processed | Pass/Fail |
| T03 | Ask a question answered in a source | Answer is grounded and cites page | Pass/Fail |
| T04 | Ask a question absent from all sources | Assistant says documents do not specify | Pass/Fail |
| T05 | Admin asks about Admin-only test PDF | Admin can retrieve synthetic test code | Pass/Fail |
| T06 | Employee asks about Admin-only test PDF | Restricted chunk is not returned in sources | Pass/Fail |
| T07 | Finance user asks about Finance-labeled document | Access follows configured Finance rule | Pass/Fail |
| T08 | Non-Finance user asks about Finance-labeled document | Access is denied by retrieval filtering | Not tested/Pass/Fail |
| T09 | Ask about contradictory policy statements | Assistant reports conflict, not a silent merge | Pass/Fail |
| T10 | Restart local app | Verify whether documents/index persist as designed | Pass/Fail |

For access-control checks, inspect retrieved sources as well as the generated answer. A refusal is not sufficient if restricted source text was still sent to the LLM.
