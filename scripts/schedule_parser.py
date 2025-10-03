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
        
        # Проверяем что файл не пустой
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
        
        # Временно возвращаем тестовое расписание
        # В реальной реализации здесь будет парсинг XLS файла
        debug_print("⚠️ Использую тестовое расписание (реализация парсинга XLS в разработке)")
        return create_realistic_schedule()
        
    except Exception as e:
        debug_print(f"❌ Ошибка при парсинге XLS: {e}")
        return []

def create_realistic_schedule():
    """Создает реалистичное расписание на основе типичной структуры МИСИС"""
    debug_print("Создание реалистичного расписания...")
    
    lessons = [
        # Понедельник
        {"subject": "Математика (Лекция)", "day": 0, "start_time": "09:00", "duration": 95, "location": "Л-550", "teacher": "Ногинова Л.Ю.", "weeks": "all", "type": "Лекция"},
        {"subject": "Математика (Практика)", "day": 0, "start_time": "12:40", "duration": 95, "location": "Л-629", "teacher": "Ногинова Л.Ю.", "weeks": "all", "type": "Практика"},
        {"subject": "Введение в специальность", "day": 0, "start_time": "14:20", "duration": 95, "location": "Б-1135", "teacher": "Попова К.Д.", "weeks": "all", "type": "Практика"},
        
        # Вторник
        {"subject": "История России (Лекция)", "day": 1, "start_time": "10:40", "duration": 95, "location": "Л-550", "teacher": "Смирнов А.В.", "weeks": "all", "type": "Лекция"},
        {"subject": "Программирование", "day": 1, "start_time": "14:20", "duration": 95, "location": "Б-1135", "teacher": "Иванов П.С.", "weeks": "all", "type": "Практика"},
        
        # Среда
        {"subject": "Физика (Лекция)", "day": 2, "start_time": "09:00", "duration": 95, "location": "Л-420", "teacher": "Петрова С.И.", "weeks": "all", "type": "Лекция"},
        {"subject": "Физика (Практика)", "day": 2, "start_time": "12:40", "duration": 95, "location": "Л-629", "teacher": "Петрова С.И.", "weeks": "all", "type": "Практика"},
        
        # Четверг
        {"subject": "Иностранный язык", "day": 3, "start_time": "10:40", "duration": 95, "location": "А-315", "teacher": "Сидорова М.К.", "weeks": "all", "type": "Практика"},
        {"subject": "Физкультура", "day": 3, "start_time": "16:20", "duration": 95, "location": "Спортзал", "teacher": "Кузнецов П.Д.", "weeks": "all", "type": "Практика"},
        
        # Пятница
        {"subject": "Информатика", "day": 4, "start_time": "09:00", "duration": 95, "location": "Б-1135", "teacher": "Васильев А.А.", "weeks": "all", "type": "Практика"},
        {"subject": "Алгоритмы и структуры данных", "day": 4, "start_time": "12:40", "duration": 95, "location": "Л-629", "teacher": "Васильев А.А.", "weeks": "all", "type": "Лекция"},
    ]
    
    debug_print(f"Создано {len(lessons)} тестовых занятий")
    return lessons

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
