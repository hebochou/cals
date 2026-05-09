import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MAX_OUTPUT=65536


def _truncate(s):
    if s is None:
        return ""
    if len(s)<=MAX_OUTPUT:
        return s
    return s[:MAX_OUTPUT]+"\n...(truncated)...\n"


def _limits():
    try:
        import resource
    except Exception:
        return None

    def _apply():
        try:
            resource.setrlimit(resource.RLIMIT_CPU,(2,2))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
        except Exception:
            pass
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE,(2*1024*1024,2*1024*1024))
        except Exception:
            pass

    return _apply


class Handler(BaseHTTPRequestHandler):
    server_version="cals-runner/1.0"

    def _send_json(self,code,obj):
        body=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path=="/health":
            return self._send_json(200,{"ok":True})
        return self._send_json(404,{"ok":False,"error":"not_found"})

    def do_POST(self):
        if self.path!="/run":
            return self._send_json(404,{"ok":False,"error":"not_found"})
        try:
            length=int(self.headers.get("Content-Length","0") or "0")
        except Exception:
            length=0
        raw=self.rfile.read(length) if length>0 else b""
        try:
            payload=json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._send_json(400,{"ok":False,"error":"bad_json"})

        code=(payload.get("code") or "")
        stdin_text=(payload.get("stdin") or "")
        compile_timeout=float(payload.get("compile_timeout") or 2.0)
        run_timeout=float(payload.get("run_timeout") or 1.5)
        if not isinstance(code,str) or not code.strip():
            return self._send_json(400,{"ok":False,"error":"empty_code"})

        workdir=tempfile.mkdtemp(prefix="cals_",dir="/tmp")
        try:
            src_path=os.path.join(workdir,"main.c")
            exe_path=os.path.join(workdir,"main")
            with open(src_path,"w",encoding="utf-8",newline="\n") as f:
                f.write(code)

            t0=time.time()
            cproc=subprocess.run(
                ["gcc","main.c","-O2","-std=c11","-Wall","-Wextra","-lm","-o","main"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=compile_timeout,
                preexec_fn=_limits(),
            )
            compile_ms=int((time.time()-t0)*1000)
            if cproc.returncode!=0:
                return self._send_json(
                    200,
                    {
                        "ok":True,
                        "compile_ok":False,
                        "run_ok":False,
                        "stdout":_truncate(cproc.stdout),
                        "stderr":_truncate(cproc.stderr),
                        "compile_ms":compile_ms,
                        "run_ms":0,
                    },
                )

            t1=time.time()
            try:
                rproc=subprocess.run(
                    [exe_path],
                    cwd=workdir,
                    input=stdin_text,
                    capture_output=True,
                    text=True,
                    timeout=run_timeout,
                    preexec_fn=_limits(),
                )
                run_ms=int((time.time()-t1)*1000)
                return self._send_json(
                    200,
                    {
                        "ok":True,
                        "compile_ok":True,
                        "run_ok":rproc.returncode==0,
                        "exit_code":rproc.returncode,
                        "stdout":_truncate(rproc.stdout),
                        "stderr":_truncate(rproc.stderr),
                        "compile_ms":compile_ms,
                        "run_ms":run_ms,
                    },
                )
            except subprocess.TimeoutExpired:
                run_ms=int((time.time()-t1)*1000)
                return self._send_json(
                    200,
                    {
                        "ok":True,
                        "compile_ok":True,
                        "run_ok":False,
                        "exit_code":None,
                        "stdout":"",
                        "stderr":"运行超时",
                        "compile_ms":compile_ms,
                        "run_ms":run_ms,
                    },
                )
        except subprocess.TimeoutExpired:
            return self._send_json(200,{"ok":True,"compile_ok":False,"run_ok":False,"stdout":"","stderr":"编译超时","compile_ms":0,"run_ms":0})
        except Exception as e:
            try:
                print(traceback.format_exc(),flush=True)
            except Exception:
                pass
            return self._send_json(500,{"ok":False,"error":"server_error","detail":str(e)})
        finally:
            try:
                shutil.rmtree(workdir,ignore_errors=True)
            except Exception:
                pass


def main():
    host=os.environ.get("RUNNER_HOST","0.0.0.0")
    port=int(os.environ.get("RUNNER_PORT","18080") or "18080")
    httpd=ThreadingHTTPServer((host,port),Handler)
    httpd.serve_forever()


if __name__=="__main__":
    main()
