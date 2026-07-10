#!/usr/bin/env python3
"""Update a Live KDP book's 7 keywords and republish. Usage: kw_update.py <ID> <kw0>..<kw6>"""
import sys, json, time
sys.path.insert(0, "/tmp")
from cdp_rw import CDP

bid = sys.argv[1]
kws = sys.argv[2:9]
assert len(kws) == 7, "need 7 keywords"
c = CDP()
base = f"https://kdp.amazon.com/action/dualbookshelf.editpaperbackdetails/en_US/title-setup/paperback/{bid}/details"

def url():
    return c.evaluate("location.href") or ""

# nav to details, clear openid handshake if needed
c.nav(base)
if "signin" in url():
    c.nav(base); time.sleep(2)
if "/details" not in url():
    print(json.dumps({"step": "nav-details", "fail": url()[:80]})); sys.exit(1)

# set keywords
setjs = """(function(){var vals=%s;var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;var o=[];vals.forEach(function(v,i){var el=document.getElementById('data-print-book-keywords-'+i);if(!el){o.push('MISS'+i);return;}s.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new Event('blur',{bubbles:true}));o.push(el.value);});return JSON.stringify(o);})()""" % json.dumps(kws)
setres = c.evaluate(setjs)

def saveAndWait(target, tries=8):
    c.evaluate("(function(){var b=document.getElementById('save-and-continue-announce');if(b)b.click();})()", gesture=True)
    for _ in range(tries):
        time.sleep(3)
        u = url()
        if target in u or "signin" in u:
            return u
    return url()

# details -> content
u1 = saveAndWait("/content")
if "signin" in u1:
    print(json.dumps({"step": "save-details", "signin": True})); sys.exit(2)
time.sleep(3)
# ensure AI checkbox if present
c.evaluate("(function(){var cb=[...document.querySelectorAll('input[type=checkbox]')].find(function(c){return /confirm that my answers are accurate/i.test(((c.closest('label')||c.parentElement||{}).textContent||''));});if(cb&&!cb.checked)cb.click();})()", gesture=True)
# content -> pricing
u2 = saveAndWait("/pricing")
if "signin" in u2:
    print(json.dumps({"step": "save-content", "signin": True})); sys.exit(2)
time.sleep(3)
# publish
c.evaluate("(function(){var b=[...document.querySelectorAll('a.a-button-text,button.a-button-text,span,button,a')].find(function(e){return /Publish Your Paperback|^Publish/i.test((e.textContent||'').trim())&&e.offsetParent!==null;});if(b)b.click();})()", gesture=True)
result = "timeout"
for _ in range(10):
    time.sleep(3)
    u = url()
    if "publishedId" in u:
        result = "published"; break
    if "signin" in u:
        result = "signin-wall"; break
print(json.dumps({"id": bid, "keywordsSet": setres, "result": result, "finalUrl": url()[:90]}))
