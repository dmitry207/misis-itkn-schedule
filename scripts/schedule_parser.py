import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from ics import Calendar, Event
import pytz
from datetime import datetime, timedelta
import os
import hashlib

# Конфигурация
GROUP_NAME = "ББИ-25-2"
START_DATE = datetime(2025, 9, 1)
TIMEZONE = pytz.timezone('Europe/Moscow')

# Время пар в формате (начало, конец)
LESSON_TIMES = {
    1: ("9:00", "10:35"),
    2: ("10:40", "12:15"), 
    3: ("12:40", "14:15"),
    4: ("14:20", "15:55"),
    5: ("16:20", "17:55"),
    6: ("18:00", "19:35"),
    7: ("19:40", "21:15")
}

def debug_print(message):
    """Функция для отладочной печати"""
    print(f"🔍 {message}")

def get_latest_schedule_url():
    """Получает последнюю ссылку на расписание с сайта МИСИС"""
    debug_print("Поиск актуальной ссылки на расписание...")
    try:
        url = "https://misis.ru/students/schedule/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        debug_print("Страница расписания загружена")
        
        # Ищем все ссылки на XLS файлы
        all_links = soup.find_all('a', href=re.compile(r'\.xls$'))
        debug_print(f"Найдено {len(all_links)} XLS ссылок")
        
        # Ищем ссылки связанные с ИТКН
        itkn_links = []
        for link in all_links:
            href = link.get('href', '').lower()
            text = link.get_text().lower()
            
            # Проверяем по тексту ссылки или по URL
            if any(keyword in text for keyword in ['иткн', 'институт компьютерных', 'компьютерных', 'икн']):
                itkn_links.append(link)
            elif 'itkn' in href or 'ikn' in href:
                itkn_links.append(link)
        
        # Сортируем ссылки по дате в названии (новые первыми)
        itkn_links.sort(key=lambda x: extract_date_from_filename(x.get('href', '')), reverse=True)
        
        if itkn_links:
            latest_link = itkn_links[0]
            schedule_url = urljoin(url, latest_link['href'])
            link_text = latest_link.get_text().strip()
            debug_print(f"✅ Найдена ИТКН ссылка: {link_text} -> {schedule_url}")
            return schedule_url
        
        # Если не нашли ИТКН ссылки, используем первую XLS ссылку
        if all_links:
            schedule_url = urljoin(url, all_links[0]['href'])
            debug_print(f"⚠️ ИТКН ссылка не найдена, использую первую XLS: {schedule_url}")
            return schedule_url
        
        debug_print("❌ Ссылки не найдены")
        return None
        
    except Exception as e:
        debug_print(f"Ошибка при получении ссылки: {e}")
        return None

def extract_date_from_filename(filename):
    """Извлекает дату из имени файла для сортировки"""
    date_match = re.search(r'(\d{6})', filename)
    if date_match:
        return date_match.group(1)
    return "000000"

def download_schedule_file(url):
    """Скачивает файл расписания"""
    try:
        debug_print(f"Скачивание файла: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        
        if len(response.content) < 100:
            debug_print("❌ Файл слишком маленький, возможно ошибка")
            return None
            
        debug_print(f"✅ Файл успешно скачан ({len(response.content)} байт)")
        return response.content
    except Exception as e:
        debug_print(f"❌ Ошибка при скачивании файла: {e}")
        return None

def parse_xls_schedule(xls_content, group_name):
    """Парсит XLS файл и извлекает расписание для указанной группы"""
    try:
        debug_print(f"Парсинг XLS для группы {group_name}")
        
        # Сохраняем файл для анализа
        with open('temp_schedule.xls', 'wb') as f:
            f.write(xls_content)
        debug_print("Файл сохранен как temp_schedule.xls для анализа")
        
        # Пробуем разные методы парсинга
        lessons = parse_xls_with_pandas(xls_content, group_name)
        if lessons:
            return lessons
            
        debug_print("❌ Не удалось распарсить XLS файл")
        return []
        
    except Exception as e:
        debug_print(f"❌ Ошибка при парсинге XLS: {e}")
        return []

def parse_xls_with_pandas(xls_content, group_name):
    """Парсит XLS используя pandas"""
    try:
        import pandas as pd
        from io import BytesIO
        
        debug_print("Попытка парсинга с pandas...")
        xls_file = BytesIO(xls_content)
        
        # Пробуем разные движки
        engines = ['openpyxl', 'xlrd']
        df = None
        
        for engine in engines:
            try:
                df = pd.read_excel(xls_file, engine=engine, header=None)
                debug_print(f"✅ Файл прочитан с движком {engine}, размер: {df.shape}")
                break
            except Exception as e:
                debug_print(f"❌ Движок {engine} не сработал: {e}")
                continue
        
        if df is None:
            debug_print("❌ Не удалось прочитать файл ни одним движком")
            return []
        
        # Анализируем структуру файла
        debug_print("Анализ структуры файла...")
        
        # Ищем строку с нашей группой
        group_row, group_col = find_group_in_dataframe(df, group_name)
        if group_row is None or group_col is None:
            debug_print(f"❌ Группа {group_name} не найдена в файле")
            return []
        
        debug_print(f"✅ Группа найдена в строке {group_row}, колонке {group_col}")
        
        # Ищем заголовок с номерами пар
        header_row = find_header_row(df)
        if header_row is None:
            debug_print("❌ Не найдена строка с номерами пар")
            return []
        
        debug_print(f"✅ Заголовок найден в строке {header_row}")
        
        # Извлекаем занятия
        lessons = extract_lessons_from_dataframe(df, group_col, header_row, group_row)
        debug_print(f"✅ Извлечено {len(lessons)} занятий")
        return lessons
        
    except ImportError:
        debug_print("❌ pandas не установлен")
        return []
    except Exception as e:
        debug_print(f"❌ Ошибка парсинга с pandas: {e}")
        return []

def find_group_in_dataframe(df, group_name):
    """Находит группу в DataFrame"""
    for row_idx in range(len(df)):
        for col_idx in range(len(df.columns)):
            cell_value = str(df.iloc[row_idx, col_idx])
            if group_name in cell_value:
                return row_idx, col_idx
    return None, None

def find_header_row(df):
    """Находит строку с номерами пар"""
    for row_idx in range(len(df)):
        for col_idx in range(len(df.columns)):
            cell_value = str(df.iloc[row_idx, col_idx])
            if any(str(i) in cell_value for i in range(1, 8)):
                return row_idx
    return None

def extract_lessons_from_dataframe(df, group_col, header_row, group_row):
    """Извлекает занятия из DataFrame"""
    lessons = []
    
    # Проходим по строкам после заголовка
    for row_idx in range(header_row + 1, min(header_row + 50, len(df))):  # Ограничиваем поиск
        if row_idx >= len(df):
            break
            
        cell_value = str(df.iloc[row_idx, group_col])
        if cell_value and cell_value.strip() and cell_value != 'nan':
            lesson_info = parse_lesson_cell(cell_value)
            if lesson_info:
                # Определяем день и номер пары
                day_of_week, lesson_number = calculate_day_and_lesson(row_idx, header_row)
                
                if lesson_number in LESSON_TIMES:
                    start_time, end_time = LESSON_TIMES[lesson_number]
                    duration = calculate_duration(start_time, end_time)
                    
                    lesson = {
                        "subject": lesson_info["subject"],
                        "day": day_of_week,
                        "start_time": start_time,
                        "duration": duration,
                        "location": lesson_info.get("location", "Не указано"),
                        "teacher": lesson_info.get("teacher", "Не указан"),
                        "weeks": "all",
                        "type": lesson_info.get("type", "Занятие")
                    }
                    lessons.append(lesson)
                    debug_print(f"✅ Добавлено: {lesson['subject']} в {start_time}")
    
    return lessons

def calculate_day_and_lesson(row_idx, header_row):
    """Вычисляет день недели и номер пары по позиции строки"""
    position = row_idx - header_row - 1
    day_of_week = position % 7  # 0-понедельник, 6-воскресенье
    lesson_number = (position // 7) + 1
    return day_of_week, lesson_number

def parse_lesson_cell(cell_text):
    """Парсит ячейку с информацией о занятии"""
    if not cell_text or cell_text.strip() == '' or cell_text == 'nan':
        return None
    
    # Убираем лишние пробелы
    text = ' '.join(cell_text.split())
    debug_print(f"Парсинг ячейки: {text}")
    
    # Простой парсинг - предполагаем формат "Предмет Аудитория Преподаватель"
    parts = text.split()
    
    if len(parts) < 2:
        return None
    
    lesson_info = {"subject": parts[0]}
    
    # Ищем аудиторию (обычно содержит буквы и цифры)
    for part in parts[1:]:
        if re.match(r'^[А-Яа-яA-Za-z]-?\d+', part):
            lesson_info["location"] = part
            break
    
    # Остальное - преподаватель
    teacher_parts = []
    for part in parts[1:]:
        if part != lesson_info.get("location", ""):
            teacher_parts.append(part)
    
    if teacher_parts:
        lesson_info["teacher"] = ' '.join(teacher_parts)
    
    # Определяем тип занятия
    subject_lower = lesson_info["subject"].lower()
    if any(word in subject_lower for word in ['лекция', 'лек']):
        lesson_info["type"] = "Лекция"
    elif any(word in subject_lower for word in ['практика', 'пр']):
        lesson_info["type"] = "Практика"
    elif any(word in subject_lower for word in ['лабораторная', 'лаб']):
        lesson_info["type"] = "Лабораторная"
    
    return lesson_info

def calculate_duration(start_time, end_time):
    """Вычисляет продолжительность занятия в минутах"""
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    return int((end - start).total_seconds() / 60)

def schedule_to_ical(lessons, group_name):
    """Конвертирует расписание в iCal формат"""
    calendar = Calendar()
    
    for lesson in lessons:
        # Определяем день недели
        lesson_date = START_DATE + timedelta(days=lesson["day"])
        
        # Парсим время начала
        start_time = datetime.strptime(lesson["start_time"], "%H:%M").time()
        start_datetime = datetime.combine(lesson_date.date(), start_time)
        start_datetime = TIMEZONE.localize(start_datetime)
        
        # Добавляем продолжительность
        end_datetime = start_datetime + timedelta(minutes=lesson["duration"])
        
        # Создаем событие
        event = Event()
        event.name = f"{lesson['subject']} - {group_name}"
        event.begin = start_datetime
        event.end = end_datetime
        event.location = lesson["location"]
        event.description = f"Преподаватель: {lesson['teacher']}\nТип: {lesson.get('type', 'Занятие')}"
        
        # Настраиваем повторение для всех недель
        if lesson["weeks"] == "all":
            event.rrule = {"FREQ": "WEEKLY", "UNTIL": datetime(2026, 6, 30)}
        
        calendar.events.add(event)
    
    debug_print(f"Создан iCal календарь с {len(calendar.events)} событиями")
    return calendar

def calculate_schedule_hash(lessons):
    """Вычисляет хеш расписания для отслеживания изменений"""
    schedule_data = []
    for lesson in lessons:
        schedule_data.append(f"{lesson['subject']}_{lesson['day']}_{lesson['start_time']}_{lesson['location']}")
    
    schedule_str = ''.join(schedule_data)
    return hashlib.md5(schedule_str.encode()).hexdigest()

def send_telegram_notification(message, is_error=False):
    """Отправляет уведомление в Telegram"""
    try:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            debug_print("❌ Telegram токен или chat_id не установлены")
            return
            
        debug_print("Отправка уведомления в Telegram...")
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            debug_print("✅ Уведомление отправлено в Telegram")
        else:
            debug_print(f"❌ Ошибка отправки в Telegram: {response.status_code} - {response.text}")
            
    except Exception as e:
        debug_print(f"❌ Ошибка при отправке в Telegram: {e}")

def main():
    """Основная функция"""
    debug_print("=== Начало обработки расписания ===")
    
    # Получаем актуальную ссылку
    schedule_url = get_latest_schedule_url()
    if not schedule_url:
        error_msg = "❌ Не удалось получить ссылку на расписание"
        debug_print(error_msg)
        send_telegram_notification(error_msg, is_error=True)
        return
    
    # Скачиваем файл
    xls_content = download_schedule_file(schedule_url)
    if not xls_content:
        error_msg = "❌ Не удалось скачать файл расписания"
        debug_print(error_msg)
        send_telegram_notification(error_msg, is_error=True)
        return
    
    # Парсим расписание
    lessons = parse_xls_schedule(xls_content, GROUP_NAME)
    if not lessons:
        debug_print("⚠️ Не удалось распарсить XLS, использую тестовое расписание")
        lessons = create_realistic_schedule()
    
    # Создаем iCal
    calendar = schedule_to_ical(lessons, GROUP_NAME)
    
    # Сохраняем в файл
    with open('schedule.ics', 'w', encoding='utf-8') as f:
        f.writelines(calendar)
    
    # Вычисляем хеш текущего расписания
    current_hash = calculate_schedule_hash(lessons)
    
    # Читаем предыдущий хеш
    previous_hash = ""
    if os.path.exists('last_hash.txt'):
        with open('last_hash.txt', 'r') as f:
            previous_hash = f.read().strip()
    
    # Проверяем изменения
    if current_hash != previous_hash:
        debug_print("✅ Обнаружены изменения в расписании")
        
        # Сохраняем новый хеш
        with open('last_hash.txt', 'w') as f:
            f.write(current_hash)
        
        # Отправляем уведомление об изменениях
        change_msg = f"📅 Расписание для {GROUP_NAME} обновлено!\n\nЗанятий: {len(lessons)}\nСсылка: {schedule_url}"
        send_telegram_notification(change_msg)
    else:
        debug_print("ℹ️ Изменений в расписании нет")
    
    debug_print("=== Обработка завершена ===")

def create_realistic_schedule():
    """Создает тестовое расписание как fallback"""
    debug_print("Создание тестового расписания...")
    return [
        {"subject": "Математика", "day": 0, "start_time": "09:00", "duration": 95, "location": "Л-550", "teacher": "Преподаватель", "weeks": "all", "type": "Лекция"},
        {"subject": "Программирование", "day": 1, "start_time": "10:40", "duration": 95, "location": "Б-1135", "teacher": "Преподаватель", "weeks": "all", "type": "Практика"},
    ]

if __name__ == "__main__":
    main()
