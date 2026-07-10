#!/usr/bin/env python3
"""cdp_force.py — robust CDP interactions for KDP controls that reject synthetic
.click() (Amazon a-button submits, custom modals). Uses TRUSTED input:
  - keyboard: focus element + Input.dispatchKeyEvent (Enter/Space)
  - box-model mouse: DOM.getBoxModel center + Input.dispatchMouseEvent click

Commands:
  diag                          print innerWidth/innerHeight/DPR
  key   <css> <Enter|Space>     focus element, send a trusted key
  click <css>                   trusted mouse click at the element's box-model center
  press <css>                   focus + Space + Enter (belt & suspenders) + box click
"""
import sys, json, time, urllib.request
import websocket

PORT = 9222

def page_ws():
    raw = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5).read()
    pages = [t for t in json.loads(raw) if t.get("type") == "page"]
    for t in pages:
        if "kdp.amazon" in (t.get("url") or ""):
            return t["webSocketDebuggerUrl"]
    return pages[0]["webSocketDebuggerUrl"]

class CDP:
    def __init__(self):
        self.ws = websocket.create_connection(page_ws(), suppress_origin=True,
                                               max_size=None, timeout=30)
        self._id = 0
        self.send("DOM.enable"); self.send("Runtime.enable")
    def send(self, method, params=None):
        self._id += 1; mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                return m
    def ev(self, expr):
        r = self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                            "awaitPromise": True, "userGesture": True})
        return r.get("result", {}).get("result", {}).get("value")
    def center(self, css):
        """Box-model center in CSS px via DOM.getBoxModel (accurate, DPR-independent)."""
        doc = self.send("DOM.getDocument", {"depth": 0})
        root = doc["result"]["root"]["nodeId"]
        q = self.send("DOM.querySelector", {"nodeId": root, "selector": css})
        nid = q.get("result", {}).get("nodeId")
        if not nid:
            return None
        bm = self.send("DOM.getBoxModel", {"nodeId": nid})
        content = bm.get("result", {}).get("model", {}).get("content")
        if not content:
            return None
        xs = content[0::2]; ys = content[1::2]
        return (sum(xs)/len(xs), sum(ys)/len(ys))
    def mouse_click(self, css):
        c = self.center(css)
        if not c:
            return "no-node"
        x, y = c
        self.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        for ev in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", {"type": ev, "x": x, "y": y,
                      "button": "left", "buttons": 1, "clickCount": 1})
        return f"clicked@{int(x)},{int(y)}"
    def key(self, css, keyname):
        self.ev(f"(function(){{var e=document.querySelector({json.dumps(css)});"
                f"if(e){{e.focus();}} return !!e;}})()")
        defs = {"Enter": ("Enter", "Enter", 13, "\r"), "Space": (" ", "Space", 32, " ")}
        k, code, vk, txt = defs[keyname]
        self.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": k, "code": code,
                  "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk})
        if txt:
            self.send("Input.dispatchKeyEvent", {"type": "char", "key": k, "text": txt,
                      "unmodifiedText": txt, "windowsVirtualKeyCode": vk})
        self.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": code,
                  "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk})
        return f"key:{keyname}"

if __name__ == "__main__":
    cmd = sys.argv[1]
    c = CDP()
    if cmd == "diag":
        print(c.ev("JSON.stringify({iw:innerWidth,ih:innerHeight,dpr:devicePixelRatio})"))
    elif cmd == "key":
        print(c.key(sys.argv[2], sys.argv[3]))
    elif cmd == "click":
        print(c.mouse_click(sys.argv[2]))
    elif cmd == "press":
        print(json.dumps({"focus_space": c.key(sys.argv[2], "Space"),
                          "enter": c.key(sys.argv[2], "Enter"),
                          "boxclick": c.mouse_click(sys.argv[2])}))
    else:
        raise SystemExit("unknown cmd")
