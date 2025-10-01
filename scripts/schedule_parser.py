import os
from ics import Calendar, Event
from datetime import datetime, timedelta

def main():
    print("🔧 Starting schedule parser...")
    
    # Создаем тестовый календарь
    calendar = Calendar()
    
    # Создаем тестовое событие
    event = Event()
    event.name = "Математика (Лекционные)"
    event.begin = datetime(2025, 9, 1, 9, 0)  # 1 сентября 2025, 9:00
    event.end = datetime(2025, 9, 1, 10, 35)  # 1 сентября 2025, 10:35
    event.location = "Л-550"
    event.description = "Группа: ББИ-25-2"
    
    calendar.events.add(event)
    
    # Сохраняем ICS файл
    with open('schedule.ics', 'w', encoding='utf-8') as f:
        f.write(calendar.serialize())
    print("✅ Created schedule.ics")
    
    # Сохраняем тестовый хэш
    with open('last_hash.txt', 'w') as f:
        f.write("test_hash_" + datetime.now().strftime("%Y%m%d%H%M%S"))
    print("✅ Created last_hash.txt")
    
    print("🎉 Parser completed successfully!")
    
    # Выводим содержимое для отладки
    print("--- schedule.ics content ---")
    with open('schedule.ics', 'r', encoding='utf-8') as f:
        print(f.read()[:200] + "...")
    
    print("--- last_hash.txt content ---")
    with open('last_hash.txt', 'r') as f:
        print(f.read())

if __name__ == "__main__":
    main()
