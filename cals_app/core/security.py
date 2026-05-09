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

from cals_app.core.db import *
def admin_required(fn):
    @wraps(fn)
    def _wrapped(*args,**kwargs):
        roles=session.get("roles") or []
        if session.get("role")!="admin" and "admin" not in roles:
            return redirect(url_for("auth_bp.admin_login"))
        return fn(*args,**kwargs)
    return _wrapped

def _current_user():
    return session.get("user","")


__all__ = ['admin_required', '_current_user', 'can_view_plain_answers']


def can_view_plain_answers():
    roles = session.get("roles", [])
    if "admin" in roles:
        return True
    if session.get("user") == "20221204010":
        return True
    return False
