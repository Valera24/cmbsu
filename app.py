import os
import json
from datetime import datetime, timedelta, date
from flask import Flask, render_template, send_from_directory, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_me'

# --- ПАРОЛЬ ПРЕПОДАВАТЕЛЯ ---
ADMIN_PASSWORD = "1234"

# --- ПУТИ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
LECTURES_FOLDER = os.path.join(STATIC_FOLDER, 'lectures')
MATERIALS_FOLDER = os.path.join(STATIC_FOLDER, 'materials')
LABS_FOLDER = os.path.join(STATIC_FOLDER, 'labs')

JSON_FILE = 'lectures.json'
DEADLINES_FILE = 'deadlines.json'
SCHEDULE_FILE = 'schedule.json'

# --- СТАНДАРТНОЕ РАСПИСАНИЕ ---
DEFAULT_SCHEDULE = {
    "semester_end": "2025-05-31",
    "classes": [
        {
            "name": "Тестовый предмет",
            "type": "lecture",
            "first_date": "2024-12-30",
            "time": "10:00 - 11:30",
            "classroom": "Ауд. 101"
        }
    ]
}


# --- ФУНКЦИИ ---
def parse_date(date_str):
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Неверный формат даты: {date_str}")


def load_json_or_create_default(filename, default_data=None):
    if not os.path.exists(filename):
        if default_data is not None:
            save_json_data(filename, default_data)
            return default_data
        return [] if filename == DEADLINES_FILE else {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not data and default_data: return default_data
            return data
    except Exception as e:
        print(f"[ERROR] Ошибка чтения {filename}: {e}")
        return default_data if default_data else {}


def save_json_data(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка записи {filename}: {e}")
        return False


def generate_schedule():
    full_schedule = []
    schedule_config = load_json_or_create_default(SCHEDULE_FILE, DEFAULT_SCHEDULE)
    semester_end_str = schedule_config.get("semester_end", "2025-05-31")
    classes_config = schedule_config.get("classes", [])

    try:
        end_date_obj = parse_date(semester_end_str)
    except ValueError:
        return []

    weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    for item in classes_config:
        try:
            current_date = parse_date(item["first_date"])
            while current_date <= end_date_obj:
                full_schedule.append({
                    "date_obj": current_date,
                    "date_str": current_date.strftime("%d.%m.%Y"),
                    "weekday": weekdays_ru[current_date.weekday()],
                    "time": item["time"],
                    "name": item["name"],
                    "type": item["type"],
                    "classroom": item.get("classroom", "")
                })
                current_date += timedelta(days=7)
        except ValueError:
            continue

    full_schedule.sort(key=lambda x: x["date_obj"])
    return full_schedule


# --- РОУТЫ ---

@app.route('/')
def index():
    semesters_data = []
    descriptions = load_json_or_create_default(JSON_FILE, {})
    priority_map = {name: index for index, name in enumerate(descriptions.keys())}
    max_priority = len(priority_map) + 1

    if os.path.exists(LECTURES_FOLDER):
        subfolders = sorted([f for f in os.listdir(LECTURES_FOLDER) if os.path.isdir(os.path.join(LECTURES_FOLDER, f))])
        for folder_name in subfolders:
            folder_path = os.path.join(LECTURES_FOLDER, folder_name)
            files = []
            for filename in os.listdir(folder_path):
                if filename.endswith('.pdf'):
                    file_info = descriptions.get(filename, {})
                    display_name = file_info.get('title', filename.replace('.pdf', '').replace('_', ' '))
                    display_desc = file_info.get('description', '')
                    relative_path = os.path.join(folder_name, filename).replace('\\', '/')
                    sort_order = priority_map.get(filename, max_priority)
                    files.append({
                        'filename': filename, 'path': relative_path, 'name': display_name,
                        'description': display_desc, 'sort_order': sort_order
                    })
            files.sort(key=lambda x: x['sort_order'])
            if files:
                title = f"{folder_name.split('_')[0]} семестр" if "sem" in folder_name else folder_name
                semesters_data.append({'title': title, 'files': files})

    return render_template('index.html', semesters=semesters_data)


@app.route('/materials')
def materials():
    files = []
    if os.path.exists(MATERIALS_FOLDER):
        for filename in os.listdir(MATERIALS_FOLDER):
            if not filename.startswith('.'):
                ext = filename.split('.')[-1].lower()
                files.append({'name': filename, 'ext': ext})
    return render_template('materials.html', files=files)


@app.route('/schedule')
def schedule():
    schedule_list = generate_schedule()
    return render_template('schedule.html', schedule=schedule_list)


@app.route('/deadlines')
def deadlines():
    raw_data = load_json_or_create_default(DEADLINES_FILE, [])
    if not isinstance(raw_data, list): raw_data = []
    labs = []
    tests = []
    today = date.today()
    for item in raw_data:
        try:
            d_obj = parse_date(item['date']).date()
            days_left = (d_obj - today).days
            if item.get('type') == 'test':
                if days_left >= 0:
                    tests.append({
                        'subject': item['subject'],
                        'title': item['title'],
                        'date_str': d_obj.strftime("%d.%m.%Y"),
                        'days_left': days_left,
                        'weekday': ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][
                            d_obj.weekday()]
                    })
            elif item.get('type') == 'lab':
                status = 'active'
                if days_left < 0: status = 'expired'
                labs.append({
                    'subject': item['subject'],
                    'title': item['title'],
                    'date_str': d_obj.strftime("%d.%m.%Y"),
                    'days_left': days_left,
                    'status': status,
                    'file': item.get('file')
                })
        except ValueError:
            continue
    tests.sort(key=lambda x: x['days_left'])
    labs.sort(key=lambda x: x['days_left'] if x['days_left'] >= 0 else 9999)
    return render_template('deadlines.html', labs=labs, tests=tests)


@app.route('/download/<path:filepath>')
def download_file(filepath):
    # Безопасная проверка всех папок
    for folder in [LECTURES_FOLDER, MATERIALS_FOLDER, LABS_FOLDER]:
        # Также проверяем подпапки лекций
        if os.path.exists(os.path.join(folder, filepath)):
            return send_from_directory(folder, filepath)
        # Если файл в подпапке (например lectures/1_sem/file.pdf)
        if folder == LECTURES_FOLDER:
            for sub in os.listdir(folder):
                if os.path.exists(os.path.join(folder, sub, filepath)):
                    return send_from_directory(os.path.join(folder, sub), filepath)
    return "Файл не найден", 404


# --- АДМИН ПАНЕЛЬ ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        flash('Неверный код доступа', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        # --- 1. ЗАГРУЗКА ФАЙЛА ---
        if 'file_upload' in request.files:
            file = request.files['file_upload']
            category = request.form.get('category')

            if file and file.filename:
                target_folder = None
                if category == 'materials':
                    target_folder = MATERIALS_FOLDER
                elif category == 'labs':
                    target_folder = LABS_FOLDER
                else:
                    target_folder = os.path.join(LECTURES_FOLDER, category)

                os.makedirs(target_folder, exist_ok=True)
                # Важно: имя файла сохраняем как есть
                filename = os.path.basename(file.filename)
                try:
                    file.save(os.path.join(target_folder, filename))
                    flash(f'Файл "{filename}" загружен!', 'success')
                except Exception as e:
                    flash(f'Ошибка: {e}', 'error')
            else:
                flash('Файл не выбран!', 'error')

        # --- 2. ДОБАВЛЕНИЕ ДЕДЛАЙНА ЧЕРЕЗ ФОРМУ (НОВОЕ!) ---
        elif 'add_deadline_btn' in request.form:
            try:
                new_task = {
                    "subject": request.form.get('subject'),
                    "title": request.form.get('title'),
                    # Формат из input type="date" всегда YYYY-MM-DD
                    "date": request.form.get('date'),
                    "type": request.form.get('type'),
                    "file": request.form.get('file_select')  # Может быть пустым
                }

                # Загружаем текущий список и добавляем
                current_deadlines = load_json_or_create_default(DEADLINES_FILE, [])
                if not isinstance(current_deadlines, list): current_deadlines = []

                current_deadlines.append(new_task)
                save_json_data(DEADLINES_FILE, current_deadlines)

                flash('Дедлайн успешно добавлен!', 'success')
            except Exception as e:
                flash(f'Ошибка добавления: {e}', 'error')

        # --- 3. СОХРАНЕНИЕ JSON ВРУЧНУЮ ---
        elif 'schedule_json' in request.form:
            try:
                if request.form.get('schedule_json'):
                    save_json_data(SCHEDULE_FILE, json.loads(request.form.get('schedule_json')))
                if request.form.get('deadlines_json'):
                    save_json_data(DEADLINES_FILE, json.loads(request.form.get('deadlines_json')))
                flash('Текстовые данные сохранены!', 'success')
            except json.JSONDecodeError:
                flash('Ошибка JSON! Проверьте запятые.', 'error')

    # --- СБОР ДАННЫХ ---
    materials_files = os.listdir(MATERIALS_FOLDER) if os.path.exists(MATERIALS_FOLDER) else []
    labs_files = os.listdir(LABS_FOLDER) if os.path.exists(LABS_FOLDER) else []

    # Фильтруем скрытые файлы
    materials_files = [f for f in materials_files if not f.startswith('.')]
    labs_files = [f for f in labs_files if not f.startswith('.')]

    semesters = []
    if os.path.exists(LECTURES_FOLDER):
        semesters = sorted([f for f in os.listdir(LECTURES_FOLDER) if os.path.isdir(os.path.join(LECTURES_FOLDER, f))])

    schedule_text = json.dumps(load_json_or_create_default(SCHEDULE_FILE, DEFAULT_SCHEDULE), ensure_ascii=False,
                               indent=4)
    deadlines_text = json.dumps(load_json_or_create_default(DEADLINES_FILE, []), ensure_ascii=False, indent=4)

    return render_template('admin.html',
                           schedule_text=schedule_text,
                           deadlines_text=deadlines_text,
                           semesters=semesters,
                           materials_files=materials_files,
                           labs_files=labs_files)


# --- НОВЫЙ РОУТ: УДАЛЕНИЕ ФАЙЛОВ ---
@app.route('/admin/delete_file', methods=['POST'])
def delete_file():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    filename = request.form.get('filename')
    category = request.form.get('category')

    target_folder = None
    if category == 'materials':
        target_folder = MATERIALS_FOLDER
    elif category == 'labs':
        target_folder = LABS_FOLDER

    if target_folder and filename:
        file_path = os.path.join(target_folder, filename)
        # Простая защита от выхода из папки
        if '..' in filename or '/' in filename:
            flash('Недопустимое имя файла', 'error')
        elif os.path.exists(file_path):
            try:
                os.remove(file_path)
                flash(f'Файл {filename} удален.', 'success')
            except Exception as e:
                flash(f'Ошибка удаления: {e}', 'error')
        else:
            flash('Файл не найден', 'error')

    return redirect(url_for('admin'))


if __name__ == '__main__':
    for folder in [LECTURES_FOLDER, MATERIALS_FOLDER, LABS_FOLDER]:
        os.makedirs(folder, exist_ok=True)
    # Создаем папки семестров по умолчанию
    for i in range(1, 4):
        os.makedirs(os.path.join(LECTURES_FOLDER, f"{i}_sem"), exist_ok=True)
    app.run()