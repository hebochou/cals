from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app

from cals_app.core.db import _db_connect

password_hasher = PasswordHasher()


def _db_ensure_default_users():
    default_class_name = '默认班级'
    default_student_no = '20221204010'
    default_student_username = default_student_no
    default_student_password = default_student_no
    default_student_display_name = '周赫博'
    conn = _db_connect()
    if not conn:
        return
    try:
        try:
            conn.autocommit(False)
        except Exception:
            pass
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO classes (name) VALUES (%s) ON DUPLICATE KEY UPDATE name=name',
                (default_class_name,),
            )
            cur.execute('SELECT id FROM classes WHERE name=%s LIMIT 1', (default_class_name,))
            class_row = cur.fetchone()
            class_id = int(class_row[0]) if class_row and class_row[0] is not None else None
            cur.execute("SELECT id FROM users WHERE username='admin' AND role='admin' LIMIT 1")
            admin_row = cur.fetchone()
            if not admin_row:
                cur.execute(
                    "INSERT INTO users (username,role,student_no,class_id,password_hash,status,created_at) VALUES (%s,'admin',NULL,NULL,%s,'active',NOW())",
                    ('admin', password_hasher.hash('admin')),
                )
            cur.execute('SELECT id FROM users WHERE student_no=%s AND role=\'student\' LIMIT 1', (default_student_no,))
            stu_row = cur.fetchone()
            if not stu_row:
                cur.execute(
                    "INSERT INTO users (username,display_name,role,student_no,class_id,password_hash,status,created_at) VALUES (%s,%s,'student',%s,%s,%s,'active',NOW())",
                    (default_student_username, default_student_display_name, default_student_no, class_id, password_hasher.hash(default_student_password)),
                )
            cur.execute('UPDATE users SET display_name=%s WHERE role=\'student\' AND student_no=%s', (default_student_display_name, default_student_no))
            cur.execute("UPDATE users SET status='disabled' WHERE role='student' AND (username='student' OR student_no='00000000000')")
        try:
            conn.commit()
        except Exception:
            pass
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            current_app.logger.error(f'db_seed_error: {exc}')
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _row_to_user(row):
    if not row:
        return None
    return {
        'id': row[0], 'username': row[1], 'display_name': row[2], 'role': row[3],
        'password_hash': row[4], 'status': row[5], 'student_no': row[6], 'class_id': row[7],
    }


def _db_get_user(username):
    conn = _db_connect()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id,username,display_name,role,password_hash,status,student_no,class_id FROM users WHERE username=%s LIMIT 1',
                ((username or '').strip(),),
            )
            return _row_to_user(cur.fetchone())
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _db_get_student_by_student_no(student_no):
    conn = _db_connect()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id,username,display_name,role,password_hash,status,student_no,class_id FROM users WHERE student_no=%s LIMIT 1',
                ((student_no or '').strip(),),
            )
            return _row_to_user(cur.fetchone())
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _db_update_user_password_hash(user_id, new_hash):
    conn = _db_connect()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET password_hash=%s WHERE id=%s', (new_hash, user_id))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _db_touch_last_login(user_id):
    conn = _db_connect()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET last_login_at=NOW() WHERE id=%s', (user_id,))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def verify_user_password(user, password):
    try:
        current_hash = user.get('password_hash', '')
        ok = password_hasher.verify(current_hash, password or '')
        if not ok:
            return False, False
        needs_rehash = password_hasher.check_needs_rehash(current_hash)
        if needs_rehash:
            user['password_hash'] = password_hasher.hash(password or '')
        return True, needs_rehash
    except VerifyMismatchError:
        return False, False
    except Exception:
        return False, False


def _db_get_user_id_by_username(username):
    conn = _db_connect()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM users WHERE username=%s LIMIT 1', ((username or '').strip(),))
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None
    finally:
        try:
            conn.close()
        except Exception:
            pass
