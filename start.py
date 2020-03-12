import os
import string
import random
import sqlite3
import csv
import datetime
import copy

import yaml
from flask import Flask, request, render_template, redirect, g

CFG = None
conn = None
cur = None
passwd = dict()
students = dict()
is_open = dict()

app = Flask(__name__)


def load_config(cfg_path='config.yaml'):
    global CFG
    with open(cfg_path, 'r') as f:
        CFG = yaml.safe_load(f)


def create_table():
    global CFG
    with app.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS CheckIn (
                       class_id TEXT NOT NULL,
                       student_num INTEGER NOT NULL,
                       month INTEGER NOT NULL,
                       day INTEGER NOT NULL);
                    ''')
        conn.commit()


def check_in_student(class_id, student_num, month, day):
    with app.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''INSERT OR REPLACE INTO CheckIn (
                       class_id, student_num, month, day) VALUES (
                       ?, ?, ?, ?);
                    ''', (class_id, student_num, month, day))
        conn.commit()


def get_passwd():
    samples = string.ascii_letters + string.digits

    return ''.join(random.sample(samples, 8))


def check_passwd():
    global CFG
    global passwd
    p = set()

    for k, v in passwd.items():
        p.add(v)

    if len(p) == len(CFG['classes']):
        return True
    return False


def gen_new_passwd():
    global CFG
    global passwd
    
    samples = string.ascii_letters + string.digits

    while not check_passwd():
        for class_obj in CFG['classes']:
            passwd[class_obj['id']] = get_passwd()
            is_open[class_obj['id']] = False


def load_students():
    global CFG
    global students

    for class_obj in CFG['classes']:
        class_id = class_obj['id']
        class_file = class_obj['file']
        with open(class_file, 'r') as f:
            reader = csv.DictReader(f)
            student_set = students.get(class_id, set())
            for row in reader:
                student_set.add(row['StudentNum'])
            students[class_id] = student_set


def check_db(class_id, student_num, month, day):
    with app.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''SELECT * FROM CheckIn WHERE
                       class_id = ? AND student_num = ? AND 
                       month = ? AND day = ?;
                    ''', (class_id, student_num, month, day))
        res = cur.fetchone()
    print(res)
    if res is not None:
        return True
    return False


def get_md():
    tz_seoul = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(tz=tz_seoul)

    return now.month, now.day


def get_db():
    global CFG
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(CFG['database'])
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


load_config()

with app.app_context():
    conn = get_db()

create_table()

load_students()

gen_new_passwd()


@app.route('/', methods=['GET'])
def index():
    global is_open
    return render_template('index.html', is_open=is_open)


@app.route('/checkin', methods=['POST'])
def check_in():
    global passwd
    global students
    global is_open

    errors = list()
    class_id = request.form.get('class_id')
    if class_id is not None:
        class_id = class_id.strip()
    if class_id not in passwd.keys():
        errors.append('학수번호-분반')
    if not is_open[class_id]:
        errors.append('시간')

    student_num = request.form.get('student_num')
    if student_num is not None:
        student_num = student_num.strip()
    if student_num not in students[class_id]:
        errors.append('학번')

    form_pass = request.form.get('passwd')
    if form_pass is not None:
        form_pass = form_pass.strip()
    if form_pass != passwd[class_id]:
        errors.append('비밀번호')

    if len(errors) > 0:
        return render_template('error.html', errors=errors)
    
    month, day = get_md()

    if check_db(class_id, student_num, month, day):
        return render_template('ok.html', already=True)
    check_in_student(class_id, student_num, month, day)
    return render_template('ok.html', already=False)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global CFG
    global is_open
    global passwd
    status = copy.deepcopy(is_open)
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        if class_id is not None:
            class_id = class_id.strip()
        form_pass = request.form.get('passwd')
        if form_pass is not None:
            form_pass = form_pass.strip()
        
        if form_pass == CFG['admin']:
            is_open[class_id] = not is_open[class_id]
        for k in is_open.keys():
            status[k] = (is_open[k], passwd[k])
    return render_template('admin.html', is_open=status)

