"""End-to-end checks for the HTTP API.  Run: python scripts/test_api.py
Stop the background worker first, or it may claim the test's job."""
import sys
sys.path.insert(0, "src")

from fastapi.testclient import TestClient
import api, db, orchestrator

client = TestClient(api.app)
PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(("  ok    " if ok else "  FAIL  ") + label +
          ("" if ok else "   got %r, want %r" % (got, want)))


print("static endpoints")
check("health", client.get("/health").status_code, 200)
tools = {t["name"]: t for t in client.get("/tools").json()["tools"]}
check("four tools", sorted(tools), ["mirtarbase", "rnahybrid", "seed", "targetscan"])
check("seed ranks 8mer first", tools["seed"]["categories"][0], "8mer")
check("rnahybrid is slow", tools["rnahybrid"]["slow"], True)
check("targetscan is lower-is-better", tools["targetscan"]["better"], "lower")

print("bad requests are refused at the gate")
check("unknown miRNA", client.post("/jobs", json={"mirna": "hsa-miR-99999"}).status_code, 404)
check("unknown tool", client.post("/jobs", json={"mirna": "hsa-miR-21-5p", "tools": ["nope"]}).status_code, 422)
check("unknown gene", client.post("/jobs", json={"mirna": "hsa-miR-21-5p", "genes": ["NOTAGENE"]}).status_code, 422)
check("unknown job", client.get("/jobs/job_nope").status_code, 404)

print("one job, end to end")
r = client.post("/jobs", json={"mirna": "hsa-miR-21-5p", "genes": ["PDCD4"],
                               "tools": ["seed", "targetscan", "mirtarbase"]})
check("accepted", r.status_code, 202)
job = r.json()["job_id"]

con = db.connect()
con.execute("UPDATE jobs SET status='running' WHERE job_id=? AND status='queued'", (job,))
con.commit()
orchestrator.run_job(con, job)

st = client.get("/jobs/" + job).json()
check("finished", st["status"], "done")
check("five records", st["n_results"], 5)

res = client.get("/jobs/%s/results" % job).json()
check("total is five", res["total"], 5)
check("8mer at 1805", [x["pos_start"] for x in res["results"]
                       if x["site_type"] == "8mer"], [1805])
check("8mer sorts first", client.get("/jobs/%s/results?tool=seed&sort=site_type"
                                     % job).json()["results"][0]["site_type"], "8mer")
check("score needs one tool", client.get("/jobs/%s/results?sort=score" % job).status_code, 422)
check("seed has no numeric score", client.get("/jobs/%s/results?sort=score&tool=seed"
                                              % job).status_code, 422)
check("context++", round(client.get("/jobs/%s/results?sort=score&tool=targetscan"
                                    % job).json()["results"][0]["score"], 3), -0.503)
check("miRTarBase extra parsed", client.get("/jobs/%s/results?tool=mirtarbase" % job)
      .json()["results"][0]["extra"]["strong_functional"], 59)
check("GAPDH is empty", client.get("/jobs/%s/results?gene=GAPDH" % job).json()["total"], 0)
check("page of two", len(client.get("/jobs/%s/results?limit=2" % job).json()["results"]), 2)

for table in ("results", "tool_runs", "jobs"):
    con.execute("DELETE FROM %s WHERE job_id=?" % table, (job,))
con.commit()

print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
