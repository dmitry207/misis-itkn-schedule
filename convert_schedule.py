import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import openpyxl
from io import BytesIO
from ics import Calendar, Event
import pytz
from datetime import datetime, timedelta
import os
import telegram
import hashlib

# Конфигурация
GROUP_NAME = "ББИ-25-2"
START_DATE = datetime(2025, 9, 1)  # 01.09.2025
TIMEZONE = pytz.timezone('Europe/Moscow')

def get_latest_schedule_url():
    """Получает последнюю ссылку на расписание с сайта МИСИС"""
    url = "https://misis.ru/students/schedule/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Ищем блок с Институтом компьютерных наук
        itkn_blocks = soup.find_all(string=re.compile(r'Институт компьютерных наук', re.IGNORECASE))
        
        for block in itkn_blocks:
            parent = block.find_parent()
            # Ищем ссылки на XLS файлы в этом блоке
            xls_links = parent.find_all('a', href=re.compile(r'\.xls$'))
            
            if xls_links:
                # Берем первую (последнюю) ссылку
                xls_link = xls_links[0]
                return urljoin(url, xls_link['href'])
        
        return None
        
    except Exception as e:
        print(f"Ошибка при получении ссылки: {e}")
        return None

def download_schedule_file(url):
    """Скачивает файл расписания"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Ошибка при скачивании файла: {e}")
        return None

def parse_xls_schedule(xls_content, group_name):
    """Парсит XLS файл и извлекает расписание для указанной группы"""
    try:
        # Загружаем Excel файл из памяти
        workbook = openpyxl.load_workbook(BytesIO(xls_content))
        sheet = workbook.active
        
        schedule_data = []
        current_date = None
        current_day = None
        
        # Проходим по всем строкам
        for row in sheet.iter_rows(values_only=True):
            # Пропускаем пустые строки
            if not any(row):
                continue
            
            # Проверяем, является ли строка датой (например, "Понедельник")
            if row[0] and isinstance(row[0], str) and any(day in row[0].lower() for day in 
                ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']):
                current_day = row[0]
                continue
            
            # Ищем занятия для нужной группы
            for i, cell in enumerate(row):
                if cell and str(cell).strip() == group_name:
                    # Нашли нашу группу, извлекаем данные о занятии
                    if i + 1 < len(row) and row[i + 1]:
                        lesson_data = {
                            'group': group_name,
                            'subject': row[i + 1],
                            'time_slot': None,
                            'week_parity': 'both'  # по умолчанию для обеих недель
                        }
                        
                        # Ищем временной слот (вернемся к началу строки)
                        if row[1] and isinstance(row[1], str) and '-' in row[1]:
                            lesson_data['time_slot'] = row[1]
                        
                        schedule_data.append(lesson_data)
        
        return schedule_data
        
    except Exception as e:
        print(f"Ошибка при парсинге XLS: {e}")
        return []

def create_ics_schedule(schedule_data, start_date):
    """Создает ICS файл из данных расписания"""
    calendar = Calendar()
    
    # Маппинг дней недели
    days_mapping = {
        'понедельник': 0,
        'вторник': 1,
        'среда': 2,
        'четверг': 3,
        'пятница': 4,
        'суббота': 5,
        'воскресенье': 6
    }
    
    # Маппинг временных слотов
    time_slots = {
        '09:00:00 - 10:35:00': (9, 0, 10, 35),
        '10:50:00 - 12:25:00': (10, 50, 12, 25),
        '12:40:00 - 14:15:00': (12, 40, 14, 15),
        '14:30:00 - 16:05:00': (14, 30, 16, 5),
        '16:20:00 - 17:55:00': (16, 20, 17, 55),
        '18:00:00 - 19:25:00': (18, 0, 19, 25),
        '19:35:00 - 21:00:00': (19, 35, 21, 0)
    }
    
    for lesson in schedule_data:
        if not lesson.get('time_slot'):
            continue
            
        time_data = time_slots.get(lesson['time_slot'])
        if not time_data:
            continue
            
        # Создаем событие для каждой недели
        event = Event()
        event.name = lesson['subject']
        event.location = lesson.get('location', 'МИСИС')
        
        # Здесь нужно добавить логику для расчета дат на основе дня недели
        # и четности недели (это упрощенная версия)
        
        calendar.events.add(event)
    
    return calendar

def send_telegram_notification(message, is_error=False):
    """Отправляет уведомление в Telegram"""
    try:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if bot_token and chat_id:
            bot = telegram.Bot(token=bot_token)
            bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        print(f"Ошибка при отправке в Telegram: {e}")

def get_file_hash(content):
    """Вычисляет хэш содержимого файла для отслеживания изменений"""
    return hashlib.md5(content).hexdigest()

def main():
    print("Запуск парсера расписания МИСИС...")
    
    # Получаем ссылку на расписание
    schedule_url = get_latest_schedule_url()
    if not schedule_url:
        error_msg = "Не удалось найти ссылку на расписание"
        send_telegram_notification(error_msg, True)
        return
    
    print(f"Найдена ссылка: {schedule_url}")
    
    # Скачиваем файл
    xls_content = download_schedule_file(schedule_url)
    if not xls_content:
        error_msg = "Не удалось скачать файл расписания"
        send_telegram_notification(error_msg, True)
        return
    
    # Проверяем, изменился ли файл
    current_hash = get_file_hash(xls_content)
    previous_hash = None
    
    try:
        with open('last_hash.txt', 'r') as f:
            previous_hash = f.read().strip()
    except FileNotFoundError:
        pass
    
    # Парсим расписание
    schedule_data = parse_xls_schedule(xls_content, GROUP_NAME)
    
    if not schedule_data:
        error_msg = f"Не найдено расписание для группы {GROUP_NAME}"
        send_telegram_notification(error_msg, True)
        return
    
    # Создаем ICS файл
    ics_calendar = create_ics_schedule(schedule_data, START_DATE)
    
    # Сохраняем ICS файл
    with open('schedule.ics', 'w', encoding='utf-8') as f:
        f.write(ics_calendar.serialize())
    
    # Сохраняем хэш текущего файла
    with open('last_hash.txt', 'w') as f:
        f.write(current_hash)
    
    # Отправляем уведомление об успехе
    if current_hash != previous_hash:
        success_msg = f"Расписание обновлено! Группа: {GROUP_NAME}\nСсылка: {schedule_url}"
        send_telegram_notification(success_msg)
        print("Расписание успешно обновлено и отправлено уведомление")
    else:
        print("Расписание не изменилось")

if __name__ == "__main__":
    main()