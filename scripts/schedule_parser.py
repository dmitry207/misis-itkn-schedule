import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from ics import Calendar, Event
import pytz
from datetime import datetime, timedelta
import os
import hashlib
import pandas as pd
from io import BytesIO

# Конфигурация
GROUP_NAME = "ББИ-25-2"
START_DATE = datetime(2025, 9, 1)
TIMEZONE = pytz.timezone('Europe/Moscow')

# Время пар в формате (начало, конец) в минутах от 0:00
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
        
        # Ищем блок "Институт компьютерных наук"
        itkn_block = None
        for element in soup.find_all(['div', 'p', 'li']):
            text = element.get_text().lower()
            if any(keyword in text for keyword in ['институт компьютерных наук', 'иткн', 'икн']):
                itkn_block = element
                debug_print("Найден блок ИТКН")
                break
        
        # Ищем все ссылки на XLS файлы в блоке ИТКН
        itkn_links = []
        if itkn_block:
            itkn_links = itkn_block.find_all('a', href=re.compile(r'\.xls$'))
            debug_print(f"Найдено {len(itkn_links)} XLS ссылок в блоке ИТКН")
        
        # Если в блоке ИТКН нет ссылок, ищем по всей странице
        if not itkn_links:
            debug_print("В блоке ИТКН нет ссылок, ищу по всей странице")
            all_links = soup.find_all('a', href=re.compile(r'\.xls$'))
            
            # Фильтруем ссылки по ключевым словам
            for link in all_links:
                href = link.get('href', '').lower()
                text = link.get_text().lower()
                
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
        
        # Если не нашли ИТКН ссылки, используем первую XLS ссылку на странице
        all_links = soup.find_all('a', href=re.compile(r'\.xls$'))
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
        
        xls_file = BytesIO(xls_content)
        
        # Пробуем разные движки для чтения
        try:
            df = pd.read_excel(xls_file, engine='openpyxl', header=None)
        except:
            try:
                df = pd.read_excel(xls_file, engine='xlrd', header=None)
            except Exception as e:
                debug_print(f"❌ Не удалось прочитать XLS файл: {e}")
                return []
        
        debug_print(f"Файл прочитан, размер: {df.shape}")
        
        # Ищем строку с заголовками (где есть номер пары)
        header_row = find_header_row(df)
        if header_row is None:
            debug_print("❌ Не найдена строка с заголовками расписания")
            return []
        
        # Ищем колонку с нашей группой
        group_col = find_group_column(df, group_name, header_row)
        if group_col is None:
            debug_print(f"❌ Группа {group_name} не найдена в файле")
            return []
        
        debug_print(f"Найдена группа в колонке {group_col}")
        return extract_lessons_from_schedule(df, group_col, header_row)
        
    except Exception as e:
        debug_print(f"❌ Ошибка при парсинге XLS: {e}")
        return []

def find_header_row(df):
    """Находит строку с заголовками (номера пар)"""
    for idx, row in df.iterrows():
        for cell in row:
            if isinstance(cell, str) and any(str(i) in str(cell) for i in range(1, 8)):
                return idx
    return None

def find_group_column(df, group_name, header_row):
    """Находит колонку с указанной группой"""
    # Ищем в строке с заголовками и нескольких следующих строках
    for row_offset in range(0, 5):
        current_row = header_row + row_offset
        if current_row >= len(df):
            break
            
        for col_idx, cell in enumerate(df.iloc[current_row]):
            if group_name in str(cell):
                return col_idx
    return None

def extract_lessons_from_schedule(df, group_col, header_row):
    """Извлекает занятия из расписания"""
    lessons = []
    
    # Проходим по строкам с занятиями (после заголовка)
    for row_idx in range(header_row + 1, len(df)):
        row = df.iloc[row_idx]
        
        # Пропускаем пустые строки
        if pd.isna(row[group_col]) or str(row[group_col]).strip() == '':
            continue
            
        lesson_info = parse_lesson_cell(str(row[group_col]))
        if lesson_info:
            # Определяем день недели по позиции строки
            day_of_week = (row_idx - header_row - 1) % 7
            
            # Определяем номер пары по позиции в дне
            lesson_number = (row_idx - header_row - 1) // 7 + 1
            
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
                    "weeks": lesson_info.get("weeks", "all"),
                    "type": lesson_info.get("type", "Занятие")
                }
                lessons.append(lesson)
                debug_print(f"Добавлено занятие: {lesson['subject']} в {start_time}")
    
    debug_print(f"Всего извлечено {len(lessons)} занятий")
    return lessons

def parse_lesson_cell(cell_text):
    """Парсит ячейку с информацией о занятии"""
    if not cell_text or cell_text.strip() == '':
        return None
    
    # Убираем лишние пробелы
    text = ' '.join(cell_text.split())
    
    # Базовый парсинг формата "Предмет Аудитория Преподаватель"
    parts = text.split()
    
    if len(parts) < 2:
        return None
    
    lesson_info = {}
    
    # Первое слово обычно предмет
    lesson_info["subject"] = parts[0]
    
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
    
    # Определяем тип занятия по названию
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
        event.name = f"{lesson['subject']} ({lesson['type']}) - {group_name}"
        event.begin = start_datetime
        event.end = end_datetime
        event.location = lesson["location"]
        event.description = f"Преподаватель: {lesson['teacher']}\nТип: {lesson['type']}"
        
        # Настраиваем повторение для всех недель
        if lesson["weeks"] == "all":
            event.rrule = {"FREQ": "WEEKLY", "UNTIL": datetime(2026, 6, 30)}
        
        calendar.events.add(event)
    
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
        error_msg = "❌ Не удалось распарсить расписание"
        debug_print(error_msg)
        send_telegram_notification(error_msg, is_error=True)
        return
    
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

if __name__ == "__main__":
    main()
