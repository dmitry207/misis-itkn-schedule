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
START_DATE = datetime(2025, 9, 1)  # Начало учебного года
END_DATE = datetime(2026, 1, 31)   # Конец семестра
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

# Русские названия дней недели для отладки
DAYS_OF_WEEK = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

def debug_print(message):
    """Функция для отладочной печати"""
    print(f"🔍 {message}")

def parse_xls_schedule(xls_content, group_name):
    try:
        debug_print(f"Парсинг XLS для группы {group_name}")
        
        import xlrd
        workbook = xlrd.open_workbook(file_contents=xls_content)
        sheet = workbook.sheet_by_index(0)
        
        debug_print(f"✅ XLS файл открыт: {sheet.nrows} строк, {sheet.ncols} колонок")
        
        # Ищем группу
        group_col = None
        for row_idx in range(sheet.nrows):
            for col_idx in range(sheet.ncols):
                cell_value = str(sheet.cell_value(row_idx, col_idx)).strip()
                if group_name in cell_value:
                    group_col = col_idx
                    debug_print(f"✅ Группа найдена: строка {row_idx}, колонка {col_idx}")
                    break
            if group_col is not None:
                break
        
        if group_col is None:
            debug_print("❌ Группа не найдена в файле")
            return []
        
        # Ищем номера пар в колонке 1
        lesson_numbers = []
        for row_idx in range(sheet.nrows):
            cell_value = str(sheet.cell_value(row_idx, 1)).strip()
            if cell_value.isdigit() and 1 <= int(cell_value) <= 7:
                lesson_numbers.append((row_idx, int(cell_value)))
        
        if not lesson_numbers:
            debug_print("❌ Не найдены номера пар")
            return []
        
        debug_print(f"✅ Найдено {len(lesson_numbers)} номеров пар")
        
        # Извлекаем занятия
        lessons = []
        current_day = -1
        last_lesson_number = 0
        
        for i, (lesson_row, lesson_number) in enumerate(lesson_numbers):
            if lesson_number in LESSON_TIMES:
                start_time, end_time = LESSON_TIMES[lesson_number]
                duration = calculate_duration(start_time, end_time)
                
                # Получаем информацию о занятии
                lesson_cell_value = str(sheet.cell_value(lesson_row, group_col)).strip()
                
                if lesson_cell_value and lesson_cell_value != 'nan' and lesson_cell_value != '':
                    lesson_info = parse_lesson_cell_detailed(lesson_cell_value)
                    if lesson_info and lesson_info["subject"] != "1":
                        # Определяем день недели: новый день начинается когда номер пары становится 1
                        if lesson_number == 1 and (last_lesson_number != 1 or i == 0):
                            current_day += 1
                        
                        last_lesson_number = lesson_number
                        
                        lesson = {
                            "subject": lesson_info["subject"],
                            "day": current_day,  # 0=понедельник, 1=вторник и т.д.
                            "start_time": start_time,
                            "duration": duration,
                            "location": lesson_info.get("location", "Не указано"),
                            "teacher": lesson_info.get("teacher", "Не указан"),
                            "type": lesson_info.get("type", "Занятие")
                        }
                        lessons.append(lesson)
                        
                        day_name = DAYS_OF_WEEK[current_day] if current_day < len(DAYS_OF_WEEK) else f"День {current_day}"
                        debug_print(f"✅ {lesson['subject']} - {day_name} {start_time} ({lesson['type']})")
        
        debug_print(f"✅ Всего извлечено {len(lessons)} занятий за {current_day + 1} дней")
        return lessons
        
    except Exception as e:
        debug_print(f"❌ Ошибка при парсинге XLS: {e}")
        import traceback
        debug_print(f"Детали ошибки: {traceback.format_exc()}")
        return []

def parse_lesson_cell_detailed(cell_text):
    """Детальный парсинг ячейки с сохранением всей информации"""
    if not cell_text or cell_text.strip() == '' or cell_text == 'nan':
        return None
    
    text = ' '.join(cell_text.strip().split())  # Убираем лишние пробелы и переносы
    
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
    
    # Ищем преподавателя в формате "Фамилия И.О."
    teacher_found = False
    for i in range(len(parts) - 1):
        if (len(parts[i]) >= 2 and 
            re.match(r'^[А-ЯЁ][а-яё]*$', parts[i]) and 
            re.match(r'^[А-ЯЁ]\.[А-ЯЁ]\.$', parts[i+1])):
            lesson_info["teacher"] = f"{parts[i]} {parts[i+1]}"
            lesson_info["subject"] = ' '.join(parts[:i])
            teacher_found = True
            break
    
    if not teacher_found:
        lesson_info["subject"] = subject
        lesson_info["teacher"] = "Не указан"
    
    # Ищем аудиторию в тексте
    location_match = re.search(r'[А-Яа-яA-Za-z]-?\d+[А-Яа-яA-Za-z]?', text)
    if location_match:
        lesson_info["location"] = location_match.group()
    else:
        lesson_info["location"] = "Не указано"
    
    return lesson_info

def calculate_duration(start_time, end_time):
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    return int((end - start).total_seconds() / 60)

def schedule_to_ical(lessons, group_name):
    """Создает iCal календарь с повторяющимися событиями"""
    calendar = Calendar()
    
    # Добавляем метаданные для календаря
    calendar.extra.append('X-WR-CALNAME:' + f'Расписание {group_name}')
    calendar.extra.append('X-WR-CALDESC:' + f'Расписание занятий для группы {group_name}')
    calendar.extra.append('X-WR-TIMEZONE:Europe/Moscow')
    
    for lesson in lessons:
        # Определяем дату первого занятия для этого дня недели
        first_lesson_date = START_DATE + timedelta(days=lesson["day"])
        
        # Парсим время начала
        start_time = datetime.strptime(lesson["start_time"], "%H:%M").time()
        start_datetime = datetime.combine(first_lesson_date.date(), start_time)
        start_datetime = TIMEZONE.localize(start_datetime)
        
        # Добавляем продолжительность
        end_datetime = start_datetime + timedelta(minutes=lesson["duration"])
        
        # Создаем событие
        event = Event()
        event.name = f"{lesson['subject']} ({lesson['type']})"
        event.begin = start_datetime
        event.end = end_datetime
        event.location = lesson["location"]
        event.description = f"Группа: {group_name}\nПреподаватель: {lesson['teacher']}\nТип: {lesson['type']}\nАудитория: {lesson['location']}"
        
        # Настраиваем еженедельное повторение до конца семестра
        event.rrule = {
            "FREQ": "WEEKLY",
            "UNTIL": END_DATE
        }
        
        calendar.events.add(event)
        
        day_name = DAYS_OF_WEEK[lesson["day"]] if lesson["day"] < len(DAYS_OF_WEEK) else f"День {lesson['day']}"
        debug_print(f"📅 Создано событие: {lesson['subject']} - каждый {day_name} {start_time}")
    
    debug_print(f"✅ Создан iCal календарь с {len(calendar.events)} повторяющимися событиями")
    return calendar

def calculate_schedule_hash(lessons):
    """Вычисляет хеш расписания для отслеживания изменений"""
    schedule_data = []
    for lesson in lessons:
        schedule_data.append(f"{lesson['subject']}_{lesson['day']}_{lesson['start_time']}_{lesson['location']}")
    
    schedule_str = ''.join(schedule_data)
    return hashlib.md5(schedule_str.encode()).hexdigest()

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
        error_msg = "❌ Не удалось распарсить расписание"
        debug_print(error_msg)
        send_telegram_notification(error_msg, is_error=True)
        return
    
    calendar = schedule_to_ical(lessons, GROUP_NAME)
    
    # Сохраняем календарь в файл
    with open('schedule.ics', 'w', encoding='utf-8') as f:
        f.writelines(calendar)
    
    debug_print("✅ Календарь сохранен как schedule.ics")
    
    # Проверяем изменения
    current_hash = calculate_schedule_hash(lessons)
    
    previous_hash = ""
    if os.path.exists('last_hash.txt'):
        with open('last_hash.txt', 'r') as f:
            previous_hash = f.read().strip()
    
    if current_hash != previous_hash:
        debug_print("✅ Обнаружены изменения в расписании")
        
        with open('last_hash.txt', 'w') as f:
            f.write(current_hash)
        
        days_count = max(lesson["day"] for lesson in lessons) + 1 if lessons else 0
        change_msg = f"📅 Расписание для {GROUP_NAME} обновлено!\n\nЗанятий: {len(lessons)}\nДней в неделе: {days_count}\nСсылка для подписки: https://raw.githubusercontent.com/dmitry207/misis-itkn-schedule/main/schedule.ics"
        send_telegram_notification(change_msg)
    else:
        debug_print("ℹ️ Изменений в расписании нет")
    
    debug_print("=== Обработка завершена ===")

if __name__ == "__main__":
    main()
