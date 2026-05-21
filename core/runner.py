# runner.py — Exécution de code à distance
import sys, gc, os, time

class _Cap:
    def __init__(self): self.buf = []
    def write(self, s): self.buf.append(str(s))
    def flush(self): pass
    def value(self): return "".join(self.buf)

def exec_code(code):
    import sys as _s
    gc.collect(); m0=gc.mem_free(); t=time.ticks_ms()
    cap=_Cap(); old=_s.stdout; _s.stdout=cap; err=None
    try:
        exec(compile(code,"<api>","exec"),{"__name__":"__exec__"})
    except Exception as e: err=str(type(e).__name__)+": "+str(e)
    finally:
        import sys as _s2; _s2.stdout=old
    gc.collect()
    return {"out":cap.value(),"err":err,
            "ms":time.ticks_diff(time.ticks_ms(),t),
            "ram":gc.mem_free(),"delta":m0-gc.mem_free()}

def run_file(name, bg=False):
    mod = name.replace(".py","")
    if "/" in mod: mod = mod.split("/")[-1]
    path = "/apps/"+mod+".py"
    try: os.stat(path)
    except:
        path = "/"+mod+".py"
        try: os.stat(path)
        except: return {"err":"Introuvable: "+mod}
    if bg:
        try:
            import _thread
            def _go():
                try:
                    if mod in sys.modules: del sys.modules[mod]
                    m=__import__(mod)
                    if hasattr(m,"run"): m.run()
                except Exception as e: print("[bg]"+str(e))
            _thread.start_new_thread(_go,())
            return {"ok":True,"mode":"bg"}
        except Exception as e: return {"err":str(e)}
    gc.collect(); t=time.ticks_ms(); err=None
    try:
        if mod in sys.modules: del sys.modules[mod]
        m=__import__(mod)
        if hasattr(m,"run"): m.run()
    except Exception as e: err=str(type(e).__name__)+": "+str(e)
    return {"ok":err is None,"ms":time.ticks_diff(time.ticks_ms(),t),"err":err}

def runnable():
    out=[]
    try:
        for f in sorted(os.listdir("/apps")):
            if f.endswith(".py") and f!="__init__.py": out.append("apps/"+f)
    except: pass
    return out
