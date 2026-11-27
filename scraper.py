"""Reads the T-BOX admin status page and writes status.json with a per-size
availability level. No locker numbers, counts or admin details are published."""
import json, os, re, sys, time
import requests

BASE = "http://tboxadmin.u-hist.com/ver1/"
SIZES = {
    "S": [1,2,3,4,6,7,8,9,33,34,35,36,38,39,40,41,43,44,45,46,48,49,50,51,53,54,55,56],
    "M": [11,12,13,15,16,17,19,20,21,23,25,26,27,29,30,31],
    "L": [5,10,37,42,47,52,57],
    "XL": [14,18,22,24,28,32],
}
FEW = {"S": 5, "M": 3, "L": 1, "XL": 1}   # "few left" at or below this many free
HEARTBEAT = 30 * 60                        # rewrite at least this often (seconds)

def text(resp):
    raw = resp.content
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("euc-kr", "replace")

def parse(html):
    """Return {locker number: True if free}."""
    out = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = [re.sub(r"<[^>]+>|&nbsp;", " ", c).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) >= 3 and cells[0].isdigit() and "사용" in cells[2]:
            out[int(cells[0])] = "미사용" in cells[2]
    return out

def levels(free):
    res = {}
    for size, nums in SIZES.items():
        n = sum(1 for i in nums if free[i])
        res[size] = "full" if n == 0 else "few" if n <= FEW[size] else "ok"
    return res

def main():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    s.post(BASE + "Member/Login.php",
           data={"UserID": os.environ["TBOX_ID"], "UserPW": os.environ["TBOX_PW"]},
           timeout=30)
    free = parse(text(s.get(BASE, params={"idx": "Control_Integrate"}, timeout=30)))
    if sorted(free) != list(range(1, 58)):
        sys.exit(f"expected lockers 1-57, read {len(free)}; nothing written")
    new = {"updated": int(time.time()), "sizes": levels(free)}
    try:
        old = json.load(open("prev.json"))
    except Exception:
        old = {}
    changed = old.get("sizes") != new["sizes"] or new["updated"] - old.get("updated", 0) >= HEARTBEAT
    json.dump(new, open("status.json", "w"))
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"changed={'true' if changed else 'false'}\n")
    print(new["sizes"], "changed" if changed else "unchanged")

if __name__ == "__main__":
    main()
