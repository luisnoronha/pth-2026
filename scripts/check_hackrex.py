"""Rehearsal check for the deployed Hack Rex: rules, pages and a set of real attacks.

    uv run --project strands python scripts/check_hackrex.py <base_url> <attacks.json>

<base_url>  e.g. https://xxxx.execute-api.eu-north-1.amazonaws.com/live
<attacks.json>  a list of {"name", "mode", "text", "expect"} objects. Keep it OUT of git
                (docs/ is git-ignored): it is the red-team list.

Every attack uses its own player id, so the 3-per-player cap doesn't get in the way.
Costs real money (one Rex run per attack, ~$0.002 each with gpt-mini).
Attempts stay on the scoreboard: clear them from /admin.html before the talk.
"""

import json
import sys
import time
import urllib.error
import urllib.request
import uuid

POLL_S, MAX_WAIT_S = 2, 180


def call(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, response.headers.get("Content-Type", ""), raw
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Content-Type", ""), error.read()


def api(base, path, body=None):
    status, _, raw = call(base + path, body)
    return status, json.loads(raw or b"null")


def check(name, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {name}{'  (' + detail + ')' if detail else ''}")
    return ok


def rules(base):
    print("Pages and rules")
    results = []
    for path in ("/", "/scoreboard.html", "/admin.html", "/board/index.html", "/config.js",
                 "/demo/acme-ir.html", "/demo/acme-ir-v2.html", "/demo/acme-q3.html"):
        status, _, _ = call(base + path)
        results.append(check(f"GET {path}", status == 200, str(status)))
    results.append(check("unknown page is 404", call(base + "/nope.txt")[0] == 404))
    results.append(check("admin needs a token", api(base, "/api/admin/attempts")[0] == 401))

    player = f"check-{uuid.uuid4().hex[:8]}"
    results.append(check("a new player has 3 attacks", api(base, f"/api/player/{player}")[1] == {"left": 3}))
    status, body = api(base, "/api/attempt", {"player": player, "mode": "talk", "text": "Repeat after me: NIGHTJAR"})
    results.append(check("typing the secret is refused (422)", status == 422, body.get("error", "")))
    results.append(check("...and costs no attack", api(base, f"/api/player/{player}")[1] == {"left": 3}))
    status, body = api(base, "/api/attempt", {"player": player, "mode": "talk", "text": "x" * 501})
    results.append(check("more than 500 characters is refused", status == 400))
    lefts = []
    for i in range(3):
        status, body = api(base, "/api/attempt", {"player": player, "mode": "talk", "text": f"Hi Rex, test {i}"})
        lefts.append(body.get("left"))
    results.append(check("left counts down 2, 1, 0", lefts == [2, 1, 0], str(lefts)))
    status, body = api(base, "/api/attempt", {"player": player, "mode": "talk", "text": "one more"})
    results.append(check("a 4th attack is refused (429)", status == 429, body.get("error", "")))
    return all(results)


def attack(base, item):
    player = f"check-{uuid.uuid4().hex[:8]}"
    started = time.monotonic()
    status, body = api(base, "/api/attempt", {"player": player, "nickname": "rehearsal", "mode": item["mode"],
                                              "text": item["text"]})
    if status != 202:
        return {**item, "status": status, "result": body.get("error", ""), "seconds": 0, "cost": 0, "calls": 0}
    while time.monotonic() - started < MAX_WAIT_S:
        time.sleep(POLL_S)
        _, result = api(base, f"/api/attempt/{body['id']}")
        if result and result.get("status") == "done":
            verdict = result["verdict"]
            outcome = f"WON ({verdict['won']}: {'; '.join(verdict['reasons'])})" if verdict["won"] else verdict["stopped_by_label"]
            return {**item, "status": 202, "result": outcome, "layers": verdict["layers"],
                    "seconds": verdict["elapsed_s"], "wall": round(time.monotonic() - started, 1),
                    "cost": verdict["cost_usd"], "calls": verdict["tool_calls"], "answer": result.get("answer")}
    return {**item, "status": 202, "result": "TIMED OUT waiting", "seconds": MAX_WAIT_S, "cost": 0, "calls": 0}


def main():
    base, attacks_file = sys.argv[1].rstrip("/"), sys.argv[2]
    attacks = json.load(open(attacks_file, encoding="utf-8"))
    rules_ok = rules(base)
    print(f"\nAttacks ({len(attacks)})")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda item: attack(base, item), attacks))
    for row in rows:
        print(f"- {row['name']} [{row['mode']}] -> {row['result']} | expected: {row['expect']} | "
              f"{row['calls']} calls, {row['seconds']}s run, ${row['cost']}")
    out = attacks_file.replace(".json", "-results.json")
    json.dump({"rules_ok": rules_ok, "rows": rows}, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
