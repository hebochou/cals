import os
import json
import random
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv
from datetime import datetime, timedelta
from functools import wraps
from html import escape as html_escape
from html.parser import HTMLParser
from flask import Flask, render_template, request, redirect, url_for, session, flash, Blueprint, current_app
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
try:
    import pymysql
except Exception:
    pymysql = None

password_hasher = PasswordHasher()

class _HTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts=[]
        self._open=[]

    def handle_starttag(self,tag,attrs):
        allowed_tags={"b","strong","i","em","u","p","br","ul","ol","li","code","pre","a","img"}
        if tag not in allowed_tags:
            return
        allowed_attrs={}
        if tag=="a":
            for k,v in attrs:
                if k in {"href","title","target","rel"} and v:
                    # 防御 javascript: 和 data: 伪协议 XSS 攻击，以及过滤 about:blank
                    if k == "href":
                        import re
                        val_lower = re.sub(r'[\s\x00-\x1f\x7f-\x9f]', '', v.lower())
                        if val_lower.startswith("javascript:") or val_lower.startswith("data:") or val_lower.startswith("vbscript:") or val_lower.startswith("about:"):
                            continue
                    allowed_attrs[k]=v
        if tag=="img":
            for k,v in attrs:
                if k in {"src","alt","title"} and v:
                    allowed_attrs[k]=v
        if tag=="img":
            src=allowed_attrs.get("src","")
            if not(src.startswith("https://") or src.startswith("http://") or src.startswith("data:image/")):
                allowed_attrs.pop("src",None)
        attr_text=""
        for k,v in allowed_attrs.items():
            attr_text+=f' {k}="{html_escape(v,quote=True)}"'
        if tag=="br" or tag=="img":
            self._parts.append(f"<{tag}{attr_text}>")
            return
        self._parts.append(f"<{tag}{attr_text}>")
        self._open.append(tag)

    def handle_endtag(self,tag):
        if self._open and self._open[-1]==tag:
            self._open.pop()
            self._parts.append(f"</{tag}>")

    def handle_data(self,data):
        if data:
            self._parts.append(html_escape(data))

    def get_html(self):
        while self._open:
            tag=self._open.pop()
            self._parts.append(f"</{tag}>")
        return "".join(self._parts)

class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts=[]

    def handle_data(self,data):
        if data:
            self._parts.append(data)

    def get_text(self):
        return "".join(self._parts)

def type_to_cn(q_type):
    if q_type=="single":
        return "单选"
    if q_type=="multi":
        return "多选"
    if q_type=="text":
        return "填空"
    if q_type=="coding":
        return "编程"
    return q_type or ""

def level_to_star(level):
    if isinstance(level,int):
        return min(5,max(1,level))
    if isinstance(level,str) and level.isdigit():
        return min(5,max(1,int(level)))
    mapping={"easy":1,"medium":3,"hard":5}
    return mapping.get(level,1)

def type_prefix(q_type):
    mapping={"single":"00","multi":"01","text":"10","coding":"11"}
    return mapping.get(q_type,"00")

def next_suffix_by_type(questions):
    counts={"single":0,"multi":0,"text":0,"coding":0}
    max_suffix={"single":0,"multi":0,"text":0,"coding":0}
    for q in questions:
        q_type=q.get("type")
        if q_type not in counts:
            continue
        counts[q_type]+=1
        code=q.get("code")
        prefix=type_prefix(q_type)
        if isinstance(code,str) and len(code)==6 and code.startswith(prefix) and code[2:].isdigit():
            max_suffix[q_type]=max(max_suffix[q_type],int(code[2:]))
    next_suffix={}
    for key in counts:
        next_suffix[key]=max(counts[key],max_suffix[key])+1
    return next_suffix

def generate_code(questions,q_type):
    suffix=next_suffix_by_type(questions).get(q_type,1)
    return f"{type_prefix(q_type)}{suffix:04d}"

def _parse_dt(text):
    if not text:
        return None
    try:
        return datetime.strptime(text,"%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def _runner_url():
    return os.getenv("RUNNER_URL", "http://127.0.0.1:18080").rstrip("/")

def _runner_post_json(path, data, timeout=10):
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        _runner_url() + path,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads((raw or b"{}").decode("utf-8", errors="ignore") or "{}")

def _unescape_sample_text(s):
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    try:
        import html
        s = html.unescape(s)
    except Exception:
        pass
    return s.replace("\r\n", "\n").replace("\r", "\n")

def _normalize_output_text(s):
    s = _unescape_sample_text(s)
    lines = s.split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    return "\n".join(ln.rstrip() for ln in lines)

def _compare_outputs(actual, expected):
    return _normalize_output_text(actual) == _normalize_output_text(expected)

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sanitize_html(raw_html):
    parser = _HTMLSanitizer()
    parser.feed(raw_html or "")
    parser.close()
    return parser.get_html()

def html_to_text(raw_html):
    parser = _HTMLTextExtractor()
    parser.feed(raw_html or "")
    parser.close()
    return parser.get_text()

def parse_tags(raw_text):
    tags = []
    seen = set()
    for part in (raw_text or "").replace("，", ",").split(","):
        tag = (part or "").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags

def tag_selection_count(tags):
    count = 0
    seen = set()
    for tag in tags or []:
        if not isinstance(tag, str):
            continue
        name = tag.strip()
        if not name:
            continue
        if ":" in name:
            cat, sub = name.split(":", 1)
            if cat.strip() and sub.strip():
                key = f"{cat.strip()}:{sub.strip()}"
            else:
                key = cat.strip() or sub.strip()
        else:
            key = name
        if key and key not in seen:
            seen.add(key)
            count += 1
    return count

def fisher_yates_shuffle(arr):
    import random
    n = len(arr)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr

def build_question_from_form(form,q_id):
    title=sanitize_html(form.get("title","").strip())
    q_type=form.get("type","").strip()
    level=form.get("level","").strip() or "1"
    tags=parse_tags(form.get("tags",""))
    explain=sanitize_html(form.get("explain","").strip())
    if not html_to_text(title).strip() or q_type not in {"single","multi","text","coding"}:
        return None
    if tag_selection_count(tags)>3:
        return None
    opt_keys=form.getlist("opt_key")
    opt_texts=form.getlist("opt_text")
    options=[]
    if q_type in {"single","multi"}:
        for key,text in zip(opt_keys,opt_texts):
            key=(key or "").strip()
            text=(text or "").strip()
            if key and text:
                options.append({"key":key,"text":text})
    if q_type=="single":
        answer=(form.get("correct","") or "").strip()
        if not answer:
            return None
    elif q_type=="multi":
        answer=[a.strip() for a in form.getlist("correct") if a.strip()]
        if not answer:
            return None
    elif q_type=="text":
        answer=(form.get("answer_text","") or "").strip()
        if answer=="":
            return None
    else:
        answer=(form.get("answer_ref","") or "").strip()
    if q_type in {"single","multi"} and not options:
        return None
    if level.isdigit():
        level=str(min(5,max(1,int(level))))
    else:
        level="1"
    return {
        "id":q_id,
        "title":title,
        "type":q_type,
        "options":options,
        "answer":answer,
        "explain":explain,
        "tags":tags,
        "level":level,
    }


__all__ = ['_HTMLSanitizer', '_HTMLTextExtractor', 'type_to_cn', 'level_to_star', 'type_prefix', 'next_suffix_by_type', 'generate_code', '_parse_dt', '_runner_url', '_runner_post_json', '_unescape_sample_text', '_normalize_output_text', '_compare_outputs', 'now_text', 'sanitize_html', 'html_to_text', 'parse_tags', 'tag_selection_count', 'fisher_yates_shuffle', 'build_question_from_form']
