#!/usr/bin/env python3
"""Write-capable CDP helper for the KDP cover-fix flow -- navigate, evaluate
JS with or without a user gesture (native clicks need one), and a
file-chooser-intercept upload helper for attaching files through KDP's UI."""
import sys, json, time, urllib.request
import websocket  # /tmp/kdpvenv

PORT = 9222

def targets():
    raw = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5).read()
    return json.loads(raw)

def page_ws():
    pages = [t for t in targets() if t.get("type") == "page"]
    if not pages:
        raise SystemExit("no page target")
    for t in pages:
        if "kdp.amazon" in (t.get("url") or ""):
            return t["webSocketDebuggerUrl"]
    for t in pages:
        if "amazon" in (t.get("url") or "").lower():
            return t["webSocketDebuggerUrl"]
    return pages[0]["webSocketDebuggerUrl"]

class CDP:
    def __init__(self):
        self.ws = websocket.create_connection(page_ws(), suppress_origin=True,
                                               max_size=None, timeout=60)
        self._id = 0
        self.events = []
    def send(self, method, params=None):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                return msg
            if "method" in msg:
                self.events.append(msg)
    def wait_event(self, method, timeout=12):
        for i, e in enumerate(self.events):
            if e.get("method") == method:
                return self.events.pop(i)
        end = time.time() + timeout
        self.ws.settimeout(timeout)
        try:
            while time.time() < end:
                msg = json.loads(self.ws.recv())
                if msg.get("method") == method:
                    return msg
        except Exception:
            pass
        finally:
            self.ws.settimeout(60)
        return None
    def nav(self, url):
        self.send("Page.enable")
        self.send("Page.navigate", {"url": url})
        self.wait_event("Page.loadEventFired", 30)
        time.sleep(2)
        return "navigated"
    def evaluate(self, expr, gesture=False):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True,
            "awaitPromise": True, "userGesture": gesture})
        res = r.get("result", {})
        if "exceptionDetails" in res:
            return {"error": str(res["exceptionDetails"])[:300]}
        return res.get("result", {}).get("value")
    def upload(self, findjs, filepath):
        self.send("Page.enable")
        self.send("DOM.enable")
        self.send("Page.setInterceptFileChooserDialog", {"enabled": True})
        clicked = self.evaluate(findjs, gesture=True)
        ev = self.wait_event("Page.fileChooserOpened", 12)
        if not ev:
            self.send("Page.setInterceptFileChooserDialog", {"enabled": False})
            return {"clicked": clicked, "chooser": None, "error": "no fileChooserOpened"}
        backend = ev["params"].get("backendNodeId")
        sf = self.send("DOM.setFileInputFiles",
                       {"files": [filepath], "backendNodeId": backend})
        self.send("Page.setInterceptFileChooserDialog", {"enabled": False})
        return {"clicked": clicked, "backendNodeId": backend,
                "setFile": "error" not in sf, "resp": sf.get("result", {})}

if __name__ == "__main__":
    cmd = sys.argv[1]
    c = CDP()
    if cmd == "nav":
        print(c.nav(sys.argv[2]))
    elif cmd == "eval":
        out = c.evaluate(sys.argv[2], gesture=False)
        print(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False))
    elif cmd == "click":
        out = c.evaluate(sys.argv[2], gesture=True)
        print(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False))
    elif cmd == "upload":
        print(json.dumps(c.upload(sys.argv[2], sys.argv[3]), ensure_ascii=False))
    elif cmd == "tap":
        # real CDP mouse click at center of element matched by JS (returns [x,y] or null)
        rect = c.evaluate(sys.argv[2])
        if not rect or not isinstance(rect, list):
            print(json.dumps({"tap": "no-rect", "got": rect})); sys.exit(0)
        x, y = rect[0], rect[1]
        for t in ("mouseMoved",):
            c.send("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y})
        c.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        c.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
        print(json.dumps({"tapped": [x, y]}))
    elif cmd == "shot":
        import base64
        r = c.send("Page.captureScreenshot", {"format": "png"})
        data = r.get("result", {}).get("data", "")
        open(sys.argv[2], "wb").write(base64.b64decode(data))
        print("saved " + sys.argv[2])
    else:
        raise SystemExit("unknown cmd")
