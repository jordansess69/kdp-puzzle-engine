#!/usr/bin/env python3
"""Attach a Live KDP book to the existing series via the /details modal flow.
Usage: series_attach.py <book_id>"""
import sys, json, time
sys.path.insert(0, "/tmp")
from cdp_rw import CDP

bid = sys.argv[1]
c = CDP()
url = f"https://kdp.amazon.com/action/dualbookshelf.editpaperbackdetails/en_US/title-setup/paperback/{bid}/details"

def cur():
    return c.evaluate("location.href") or ""

# nav with handshake retry
for _ in range(3):
    c.nav(url); time.sleep(2)
    if "/details" in cur() and "signin" not in cur():
        break
if "/details" not in cur():
    print(json.dumps({"id": bid, "fail": "not on details", "url": cur()[:80]})); sys.exit(1)

# already in series?
if c.evaluate("/Large Print Puzzles for Adults & Seniors/i.test(document.body.innerText)"):
    print(json.dumps({"id": bid, "result": "already-in-series"})); sys.exit(0)

def clk(js):
    return c.evaluate(js, gesture=True)

def realtap(findjs):
    rect = c.evaluate(findjs)
    if not rect or not isinstance(rect, list):
        return False
    x, y = rect
    c.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    c.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    c.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    return True

# Add to series
clk("(function(){var b=document.querySelector('#a-autoid-2-announce');if(b)b.click();})()"); time.sleep(3)
# Select series (existing)
clk("(function(){var b=[...document.querySelectorAll('button,span,a')].find(e=>/^Select series$/i.test((e.textContent||'').trim())&&e.offsetParent!==null);if(b)b.click();})()"); time.sleep(3)
# click the series card (real input click at center)
tapped = realtap("(function(){var l=[...document.querySelectorAll('*')].find(e=>/live title/i.test(e.textContent||'')&&(e.textContent||'').length<60);if(!l)return null;var card=l.closest('.a-box')||l.parentElement;var r=card.getBoundingClientRect();return [Math.round(r.left+r.width/2),Math.round(r.top+r.height/2)];})()")
time.sleep(3)
# Main content
clk("(function(){var b=[...document.querySelectorAll('button,span,a')].find(e=>/^Main content$/i.test((e.textContent||'').trim())&&e.offsetParent!==null);if(b)b.click();})()"); time.sleep(3)
# Confirm and continue
clk("(function(){var b=[...document.querySelectorAll('button,span,a')].find(e=>/^Confirm and continue$/i.test((e.textContent||'').trim())&&e.offsetParent!==null);if(b)b.click();})()"); time.sleep(5)

signin = "signin" in cur()
nameShown = c.evaluate("/Large Print Puzzles for Adults & Seniors/i.test(document.body.innerText)")
print(json.dumps({"id": bid, "cardTapped": tapped, "signinWall": signin, "seriesNameOnDetails": bool(nameShown),
                  "result": "attached" if nameShown and not signin else ("signin-wall" if signin else "uncertain")}))
