"""Reads the T-BOX admin status page and publishes status.json with a per-size
availability level. No locker numbers, counts or admin details are published.
Runs as a loop: reads every READ_EVERY seconds for RUN_FOR seconds."""
import json, os, re, shutil, subprocess, sys, time
import requests

BASE = "http://tboxadmin.u-hist.com/ver1/"
SIZES = {
    "S": [1,2,3,4,6,7,8,9,33,34,35,36,38,39,40,41,43,44,45,46,48,49,50,51,53,54,55,56],
    "M": [11,12,13,15,16,17,19,20,21,23,25,26,27,29,30,31],
    "L": [5,10,37,42,47,52,57],
    "XL": [14,18,22,24,28,32],
}
FEW = {"S": 5, "M": 3, "L": 1, "XL": 1}          # "few left" at or below this many free
READ_EVERY = int(os.environ.get("READ_EVERY", "120"))   # seconds between reads
HEARTBEAT = int(os.environ.get("HEARTBEAT", "600"))     # publish at least this often
RUN_FOR = int(os.environ.get("RUN_FOR", "18000"))       # one round lasts this long

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

def login(s):
    s.get(BASE + "Member/Login.php", timeout=30)
    s.post(BASE + "Member/login_in.php",
           data={"UserID": os.environ["TBOX_ID"].strip(), "UserPW": os.environ["TBOX_PW"].strip(),
                 "idSave": "0", "passwordSave": "0"},
           headers={"Referer": BASE + "Member/Login.php"}, timeout=30)

def read(s):
    """Read the status page, logging in again only when the session has expired."""
    for attempt in (1, 2):
        free = parse(text(s.get(BASE, params={"idx": "Control_Integrate"}, timeout=30)))
        if sorted(free) == list(range(1, 58)):
            return levels(free)
        if attempt == 1:
            login(s)
    raise RuntimeError(f"expected lockers 1-57, read {len(free)}")

def publish(status):
    shutil.rmtree("pub", ignore_errors=True)
    os.makedirs("pub")
    json.dump(status, open("pub/status.json", "w"))
    cmds = [["git", "init", "-q", "-b", "status"],
            ["git", "config", "user.name", "status-bot"],
            ["git", "config", "user.email", "status-bot@users.noreply.github.com"],
            ["git", "add", "status.json"],
            ["git", "commit", "-qm", "status"],
            ["git", "push", "-qf", os.environ["PUSH_URL"], "status"]]
    for c in cmds:
        subprocess.run(c, cwd="pub", check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    try:
        last = json.load(open("prev.json"))
    except Exception:
        last = {}
    end, ok = time.time() + RUN_FOR, 0
    while True:
        try:
            sizes = read(s)
            now = int(time.time())
            if sizes != last.get("sizes") or now - last.get("updated", 0) >= HEARTBEAT:
                status = {"updated": now, "sizes": sizes}
                publish(status)
                last = status
                print(time.strftime("%H:%M:%S"), "published", sizes, flush=True)
            ok += 1
        except Exception as e:
            print(time.strftime("%H:%M:%S"), "read failed:", type(e).__name__, flush=True)
        if time.time() + READ_EVERY >= end:
            break
        time.sleep(READ_EVERY)
    if not ok:
        sys.exit("no successful read in this round")

if __name__ == "__main__":
    main()
