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
from cals_app.core.security import *
from cals_app.utils.helpers import *
from cals_app.services.logic import *

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route("/")
# 入口路由：重定向到学生登录页并返回响应。
def index():
    if session.get("user"):
        if session.get("role")=="admin":
            return redirect(url_for("admin_bp.admin_dashboard"))
        return redirect(url_for("student_bp.student_home"))
    return redirect(url_for("auth_bp.login"))

@auth_bp.route("/login",methods=["GET","POST"])
# 学生登录：校验成功重定向，否则返回登录页渲染响应。
def login():
    if session.get("user"):
        if session.get("role")=="admin":
            return redirect(url_for("admin_bp.admin_dashboard"))
        return redirect(url_for("student_bp.student_home"))
    _db_ensure_default_users()
    if request.method=="POST":
        username=request.form.get("username","").strip()
        password=request.form.get("password","")
        _db_ensure_default_users()
        if username.isdigit() and len(username)==11:
            u=_db_get_student_by_student_no(username)
        else:
            u=_db_get_user(username)
            if not u or u.get("role")!="admin":
                flash("请输入 11 位学号","error")
                return render_template("login.html")
        ok,rehashed=(verify_user_password(u,password) if u else(False,False))
        if not u or u.get("role") not in {"student","admin"} or u.get("status")!="active" or not ok:
            flash("账号或密码错误","error")
            return render_template("login.html")
        if rehashed:
            _db_update_user_password_hash(u["id"],u.get("password_hash",""))
        _db_touch_last_login(u["id"])
        session["user"]=u["username"]
        session["display_name"]=u.get("display_name") or u.get("username")
        session["role"]="student"
        roles=["student"]
        if u.get("role")=="admin":
            roles.append("admin")
        session["roles"]=roles

        return redirect(url_for("student_bp.student_home"))
    return render_template("login.html")

@auth_bp.route("/logout")
# 退出登录：清空 session 并返回重定向响应。
def logout():
    session.clear()
    return redirect(url_for("auth_bp.login"))

@auth_bp.route("/admin/login",methods=["GET","POST"])
# 管理员登录：校验成功重定向，否则返回登录页渲染响应。
def admin_login():
    if session.get("user"):
        if session.get("role")=="admin":
            return redirect(url_for("admin_bp.admin_dashboard"))
        return redirect(url_for("student_bp.student_home"))
    _db_ensure_default_users()
    if request.method=="POST":
        username=request.form.get("username","").strip()
        password=request.form.get("password","").strip()
        _db_ensure_default_users()
        u=_db_get_user(username)
        ok,rehashed=(verify_user_password(u,password) if u else(False,False))
        if not u or u.get("role")!="admin" or u.get("status")!="active" or not ok:
            flash("账号或密码错误","error")
            return render_template("admin/login.html")
        if rehashed:
            _db_update_user_password_hash(u["id"],u.get("password_hash",""))
        _db_touch_last_login(u["id"])
        session["role"]="admin"
        session["user"]=u["username"]
        session["display_name"]=u.get("display_name") or u.get("username")
        session["roles"]=["admin","student"]
        return redirect(url_for("admin_bp.admin_dashboard"))
    return render_template("admin/login.html")


__all__ = ['index', 'login', 'logout', 'admin_login']
