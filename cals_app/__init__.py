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


def create_app():
    load_dotenv()
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    from cals_app.routes.auth import auth_bp
    from cals_app.routes.student import student_bp
    from cals_app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    return app
