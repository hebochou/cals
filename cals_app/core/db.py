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

def _db_settings():
    password=os.environ.get("CALS_DB_PASSWORD","").strip()
    host=os.environ.get("CALS_DB_HOST","127.0.0.1").strip() or "127.0.0.1"
    port_raw=os.environ.get("CALS_DB_PORT","3306").strip() or "3306"
    port=int(port_raw) if port_raw.isdigit() else 3306
    user=os.environ.get("CALS_DB_USER","cals_user").strip() or "cals_user"
    db=os.environ.get("CALS_DB_NAME","cals").strip() or "cals"
    return {"host":host,"port":port,"user":user,"password":password,"db":db}

def _db_connect():
    if not pymysql:
        return None
    cfg=_db_settings()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["db"],
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=2,
        read_timeout=2,
        write_timeout=2,
    )


__all__ = ['_db_settings', '_db_connect']
