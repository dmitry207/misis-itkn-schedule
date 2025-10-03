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
            
            if any(keyword in text for keyword in ['иткн', 'институт компьютерных', 'компьютерных', 'икн']):
                itkn_links.append(link)
            elif 'itkn' in href or 'ikn' in href:
                itkn_links.append(link)
        
        itkn_links.sort(key=lambda x: extract_date_from_filename(x.get('href', '')), reverse=True)
        
        if itkn_links:
            latest_link = itkn_links[0]
            schedule_url = urljoin(url, latest_link['href'])
            link_text = latest_link.get_text().strip()
            debug_print(f"✅ Найдена ИТКН ссылка: {link_text} -> {schedule_url}")
            return schedule_url
        
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
    date_match = re.search(r'(\d{6})', filename)
    if date_match:
        return date_match.group(1)
    return "000000"

def download_schedule_file(url):
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
    try:
        debug_print(f"Парсинг XLS для группы {group_name}")
        
        import xlrd
        workbook = xlrd.open_workbook(file_contents=xls_content)
        sheet = workbook.sheet_by_index(0)
        
        debug_print(f"✅ XLS файл открыт: {sheet.nrows} строк, {sheet.ncols} колонок")
        
        # Ищем группу в файле
        group_col = None
        for row_idx in range(sheet.nrows):
            for col_idx in range(sheet.ncols):
                cell_value = str(sheet.cell_value(row_idx, col_idx))
                if group_name in cell_value:
                    group_col = col_idx
                    debug_print(f"✅ Группа найдена в строке {row_idx}, колонке {col_idx}")
                    break
            if group_col is not None:
                break
        
        if group_col is None:
            debug_print("❌ Группа не найдена в файле")
            return []
        
        # Ищем заголовок с днями недели (обычно в строке 1)
        days_header_row = 1
        debug_print(f"✅ Используем строку {days_header_row} как заголовок дней недели")
        
        # Ищем номера пар в первом столбце
        lessons_column = 0
        debug_print(f"✅ Используем колонку {lessons_column} для номеров пар")
        
        # Извлекаем занятия
        lessons = []
        current_day = -1
        
        for row_idx in range(2, sheet.nrows):  # Начинаем с строки 2 (после заголовков)
            # Проверяем ячейку с номером пары
            lesson_cell = str(sheet.cell_value(row_idx, lessons_column)).strip()
            
            # Если это номер пары (1, 2, 3...)
            if lesson_cell and lesson_cell.isdigit():
                lesson_number = int(lesson_cell)
                if lesson_number in LESSON_TIMES:
                    start_time, end_time = LESSON_TIMES[lesson_number]
                    duration = calculate_duration(start_time, end_time)
                    
                    # Получаем информацию о занятии
                    lesson_cell_value = str(sheet.cell_value(row_idx, group_col)).strip()
                    
                    if lesson_cell_value and lesson_cell_value != 'nan' and lesson_cell_value != '':
                        lesson_info = parse_lesson_cell_detailed(lesson_cell_value)
                        if lesson_info:
                            # Определяем день недели по строке дня
                            day_cell = str(sheet.cell_value(days_header_row, group_col)).strip()
                            day_of_week = parse_day_of_week(day_cell, row_idx, days_header_row)
                            
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
                            debug_print(f"✅ {lesson['subject']} ({lesson['type']}) - {start_time} (день {day_of_week})")
        
        debug_print(f"✅ Всего извлечено {len(lessons)} занятий")
        return lessons
        
    except Exception as e:
        debug_print(f"❌ Ошибка при парсинге XLS: {e}")
        return []

def parse_day_of_week(day_cell, row_idx, header_row):
    """Определяет день недели на основе структуры файла"""
    # Простая логика - каждая следующая группа строк это новый день
    day_offset = (row_idx - header_row - 2) // 7  # 7 пар в день
    return day_offset % 7

def parse_lesson_cell_detailed(cell_text):
    """Детальный парсинг ячейки с сохранением всей информации"""
    if not cell_text or cell_text.strip() == '' or cell_text == 'nan':
        return None
    
    text = cell_text.strip()
    debug_print(f"🔍 Парсинг: '{text}'")
    
    lesson_info = {}
    
    # Извлекаем тип занятия
    if '(Лекционные)' in text:
        lesson_info["type"] = "Лекция"
        subject = text.replace('(Лекционные)', '').strip()
    elif '(Практические)' in text:
        lesson_info["type"] = "Практика" 
        subject = text.replace('(Практические)', '').strip()
    elif '(Лабораторные)' in text:
        lesson_info["type"] = "Лабораторная"
        subject = text.replace('(Лабораторные)', '').strip()
    else:
        lesson_info["type"] = "Занятие"
        subject = text
    
    # Разделяем предмет и преподавателя
    parts = subject.split()
    if len(parts) >= 3:  # Есть достаточно частей для преподавателя
        # Предполагаем, что преподаватель в конце (Фамилия И. О.)
        if re.match(r'^[А-ЯЁ][а-яё]*\s[А-ЯЁ]\.[А-ЯЁ]\.$', ' '.join(parts[-2:])):
            lesson_info["teacher"] = ' '.join(parts[-2:])
            lesson_info["subject"] = ' '.join(parts[:-2])
        else:
            lesson_info["subject"] = subject
            lesson_info["teacher"] = "Не указан"
    else:
        lesson_info["subject"] = subject
        lesson_info["teacher"] = "Не указан"
    
    # Ищем аудиторию в тексте (если есть)
    location_match = re.search(r'[А-Яа-яA-Za-z]-?\d+[А-Яа-яA-Za-z]?', text)
    if location_match:
        lesson_info["location"] = location_match.group()
    
    return lesson_info

def calculate_duration(start_time, end_time):
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    return int((end - start).total_seconds() / 60)

def schedule_to_ical(lessons, group_name):
    calendar = Calendar()
    
    for lesson in lessons:
        lesson_date = START_DATE + timedelta(days=lesson["day"])
        
        start_time = datetime.strptime(lesson["start_time"], "%H:%M").time()
        start_datetime = datetime.combine(lesson_date.date(), start_time)
        start_datetime = TIMEZONE.localize(start_datetime)
        
        end_datetime = start_datetime + timedelta(minutes=lesson["duration"])
        
        event = Event()
        event.name = f"{lesson['subject']} ({lesson['type']}) - {group_name}"
        event.begin = start_datetime
        event.end = end_datetime
        event.location = lesson["location"]
        event.description = f"Преподаватель: {lesson['teacher']}\nТип: {lesson['type']}\nАудитория: {lesson['location']}"
        
        if lesson["weeks"] == "all":
            event.rrule = {"FREQ": "WEEKLY", "UNTIL": datetime(2026, 6, 30)}
        
        calendar.events.add(event)
    
    debug_print(f"Создан iCal календарь с {len(calendar.events)} событиями")
    return calendar

def calculate_schedule_hash(lessons):
    schedule_data = []
    for lesson in lessons:
        schedule_data.append(f"{lesson['subject']}_{lesson['day']}_{lesson['start_time']}_{lesson['location']}")
    
    schedule_str = ''.join(schedule_data)
    return hashlib.md5(schedule_str.encode()).hexdigest()

def send_telegram_notification(message, is_error=False):
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
    debug_print("=== Начало обработки расписания ===")
    
    schedule_url = get_latest_schedule_url()
    if not schedule_url:
        error_msg = "❌ Не удалось получить ссылку на расписание"
        debug_print(error_msg)
        send_telegram_notification(error_msg, is_error=True)
        return
    
    xls_content = download_schedule_file(schedule_url)
    if not xls_content:
        error_msg = "❌ Не удалось скачать файл расписания"
        debug_print(error_msg)
        send_telegram_notification(error_msg, is_error=True)
        return
    
    lessons = parse_xls_schedule(xls_content, GROUP_NAME)
    if not lessons:
        debug_print("❌ Не удалось распарсить расписание")
        return
    
    calendar = schedule_to_ical(lessons, GROUP_NAME)
    
    with open('schedule.ics', 'w', encoding='utf-8') as f:
        f.writelines(calendar)
    
    current_hash = calculate_schedule_hash(lessons)
    
    previous_hash = ""
    if os.path.exists('last_hash.txt'):
        with open('last_hash.txt', 'r') as f:
            previous_hash = f.read().strip()
    
    if current_hash != previous_hash:
        debug_print("✅ Обнаружены изменения в расписании")
        
        with open('last_hash.txt', 'w') as f:
            f.write(current_hash)
        
        change_msg = f"📅 Расписание для {GROUP_NAME} обновлено!\n\nЗанятий: {len(lessons)}\nСсылка: {schedule_url}"
        send_telegram_notification(change_msg)
    else:
        debug_print("ℹ️ Изменений в расписании нет")
    
    debug_print("=== Обработка завершена ===")

if __name__ == "__main__":
    main()
