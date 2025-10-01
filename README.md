# MISIS Schedule Parser v1.0.0

[![GitHub Actions](https://github.com/dmitry207/misis-itkn-schedule/actions/workflows/schedule.yml/badge.svg)](https://github.com/dmitry207/misis-itkn-schedule/actions)
![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)

Автоматизированная система для парсинга расписания МИСИС...
# MISIS Schedule Parser

Автоматизированная система для парсинга расписания МИСИС и преобразования его в формат iCalendar (.ics).

## Функциональность

- 📅 Автоматическое получение актуального расписания с сайта МИСИС
- 🔄 Преобразование XLS расписания в формат iCalendar
- 🤖 Автоматические обновления через GitHub Actions
- 📱 Уведомления в Telegram об изменениях
- 📲 Подписка на календарь через ссылку

## Настройка

### 1. Telegram бот

1. Создайте бота через @BotFather
2. Получите токен бота
3. Добавьте токен в секреты GitHub как `TELEGRAM_BOT_TOKEN`
4. Получите ваш Chat ID и добавьте как `TELEGRAM_CHAT_ID`

### 2. GitHub Secrets

В настройках репозитория добавьте:
- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота
- `TELEGRAM_CHAT_ID` - ваш Chat ID в Telegram

## Использование

### Подписка на календарь

Добавьте в ваш календарь ссылку:
