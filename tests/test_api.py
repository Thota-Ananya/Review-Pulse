import io


def test_health_and_seed(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["reviews"] > 2000


def test_dashboard_kpis_are_consistent(client):
    d = client.get("/api/dashboard").json()
    k = d["kpis"]
    assert 1 <= k["avg_rating"] <= 5
    assert 0 <= k["pct_negative"] <= 1
    assert sum(w["reviews"] for w in d["trend"]) == k["total_reviews"]
    assert sum(c["reviews"] for c in d["cities"]) == k["total_reviews"]


def test_filter_by_city(client):
    allk = client.get("/api/dashboard").json()["kpis"]["total_reviews"]
    hyd = client.get("/api/dashboard", params={"city": "Hyderabad"}).json()
    assert 0 < hyd["kpis"]["total_reviews"] < allk
    assert [c["segment"] for c in hyd["cities"]] == ["Hyderabad"]


def test_insights_find_planted_problems(client):
    titles = " | ".join(i["title"] for i in client.get("/api/insights").json()["insights"])
    assert "App Experience complaints spiking on iOS" in titles
    assert "Delivery complaints spiking in Hyderabad" in titles
    assert "Pricing" in titles


def test_summary_falls_back_to_rules_without_key(client):
    s = client.get("/api/summary").json()
    assert s["source"] == "rules" and len(s["summary"]) > 20


def test_reviews_pagination_and_filters(client):
    r = client.get("/api/reviews", params={"topic": "Refunds", "sentiment": "negative", "size": 5}).json()
    assert r["total"] > 0 and len(r["items"]) == 5
    assert all("Refunds" in x["topics"] and x["sentiment"] == "negative" for x in r["items"])


def test_reviews_rejects_bad_sentiment(client):
    assert client.get("/api/reviews", params={"sentiment": "angry"}).status_code == 422


def test_search_is_injection_safe(client):
    r = client.get("/api/reviews", params={"q": "'; DROP TABLE reviews; --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/api/health").json()["reviews"] > 0


def test_export_csv(client):
    r = client.get("/api/export.csv", params={"city": "Pune"})
    assert r.status_code == 200 and r.text.startswith("review_id,date")


def test_upload_validates_and_skips_bad_rows(client):
    csv = ("review_text,rating,date,city\n"
           "Food was cold and late,1,2026-10-10,Hyderabad\n"
           ",5,2026-10-10,Pune\n"            # empty text -> skipped
           "Great app,9,2026-10-10,Pune\n"   # rating out of range -> skipped
           "Nice packaging,5,not-a-date,Pune\n")  # bad date -> skipped
    r = client.post("/api/upload", files={"file": ("r.csv", io.BytesIO(csv.encode()), "text/csv")})
    assert r.status_code == 200
    assert r.json() == {"rows_received": 4, "inserted": 1, "skipped_invalid": 3}


def test_upload_missing_columns(client):
    r = client.post("/api/upload", files={"file": ("r.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")})
    assert r.status_code == 422 and "review_text" in r.json()["detail"]


def test_upload_rejects_non_csv(client):
    r = client.post("/api/upload", files={"file": ("r.txt", io.BytesIO(b"x"), "text/plain")})
    assert r.status_code == 400


def test_reset_demo(client):
    r = client.post("/api/reset-demo").json()
    assert r["inserted"] == client.get("/api/health").json()["reviews"]
