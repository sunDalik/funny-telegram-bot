from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler
import random
import redis_db
from utils import in_whitelist
from datetime import datetime, timedelta, time
import logging
from time import sleep
from main import opinion, getDict, DICTIONARY_HASH, GIF_PREFIX, STICKER_PREFIX

logger = logging.getLogger(__name__)
r = redis_db.connect()

def random_cope(update: Update, context):
    if (not in_whitelist(update)):
        return
    options = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33]
    weights = [100, 100, 100, 100, 60, 0.1, 100, 4, 50, 15, 3, 3, 40, 15, 20, 1, 6, 6, 6, 1.5, 1.5, 35, 20, 90, 50, 90, 100, 12, 1, 0.5, 0.5, 0.5, 0.5]
    res = random.choices(options, weights=weights)[0]
    logger.info(f"[cope] res {res}")
    if res == 1:
        update.message.reply_text(f"Найс коупишь", quote=False)
    elif res == 2:
        update.message.reply_text(f"Коуп жиденький", quote=False)
    elif res == 3:
        update.message.reply_text(f"Коуп хороший\nЗдорово покоупил", quote=False)
    elif res == 4:
        update.message.reply_text(f"Коуп плохой\nКоупи лучше", quote=False)
    elif res == 5:
        update.message.reply_text(f"Коуп отвратительный", quote=False)
    elif res == 6:
        update.message.reply_text(f"=== ЛЕГЕНДАРНЫЙ КОУП ===\nЭтот коуп войдет в историю!\nПоздравляем @{update.message.from_user.username} с получением этого невероятного редкого коупа", quote=False)
    elif res == 7:
        update.message.reply_text(f"Коуп слабый\nКоупи сильнее", quote=False)
    elif res == 8:
        update.message.reply_text(f"Тариф Гигакоупище\nБезлимитный коуп по всей России", quote=False)
    elif res == 9:
        update.message.reply_text(f"Лютейший коуп", quote=False)
    elif res == 10:
        update.message.reply_text(f"Удачный коуп!\nМожешь еще раз покоупить", quote=False)
    elif res == 11:
        update.message.reply_text(f"Этот божественный коуп настолько силен, что способен излучать ауру добра и позитива, которая увеличивает силу коупа друзей на 50%", quote=False)
    elif res == 12:
        update.message.reply_text(f"Выбираем главного коупера дня", quote=False)
        sleep(1.5)
        update.message.reply_text(random.choice(["Хмм...", "Так-так-так...", "Расшифровываю результаты...", "Спрашиваем мнения экспертов...", "Дайте подумать..."]), quote=False)
        sleep(1.5)
        update.message.reply_text(f"А вот и победитель - @{update.message.from_user.username}!", quote=False)
    elif res == 13:
        update.message.reply_text(f"Как же он сильно коупит...\nПарень полегче!", quote=False)
    elif res == 14:
        update.message.reply_text(f"Критически плохой коуп!\nУ тебя весь день будет ФОМО", quote=False)
    elif res == 15:
        update.message.reply_text(f"Отличный коуп!\nВсе проблемы решены", quote=False)
    elif res == 16:
        update.message.reply_text(f"Шедевральный коуп!\nО нем напишут в книгах", quote=False)
    elif res == 17:
        update.message.reply_text(f"Я не вижу вашего коупа", quote=False)
    elif res == 18:
        values = list(r.hgetall(DICTIONARY_HASH).values())
        values = [val for val in values if val.startswith(STICKER_PREFIX)]
        if len(values) == 0:
            update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", quote=False)
            return
        random.shuffle(values)
        file_id = values[0][len(STICKER_PREFIX):]
        logger.info(f"fileid {file_id}")
        update.message.reply_sticker(file_id, quote=False)
    elif res == 19:
        values = list(r.hgetall(DICTIONARY_HASH).values())
        values = [val for val in values if val.startswith(GIF_PREFIX)]
        if len(values) == 0:
            update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", quote=False)
            return
        random.shuffle(values)
        file_id = values[0][len(GIF_PREFIX):]
        logger.info(f"fileid {file_id}")
        update.message.reply_animation(file_id, quote=False)
    elif res == 20:
        update.message.reply_text(f"Кто-то сомневается в твоем коупе? Вызови его на дуэль в /rockpaperscissors и посмотри чей коуп победит!", quote=False)
    elif res == 21:
        update.message.reply_text(f"Кто-то сомневается в твоем коупе? Вызови его на дуэль в /connectfour и посмотри чей коуп победит!", quote=False)
    elif res == 22:
        keys = list(r.hgetall(DICTIONARY_HASH).keys())
        keys = [key for key in keys if key.lower().startswith("коуп")]
        if len(keys) == 0:
            update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", quote=False)
            return
        random.shuffle(keys)
        key = keys[0]
        update.message.reply_text(f"/get {key}", quote=False)
        sleep(0.5)
        logger.info(f"cope get {key}")
        update.message.text = f"/get {key}"
        getDict(update, context)
    elif res == 23:
        update.message.text = "/opinion коуп"
        opinion(update, context)
    elif res == 24:
        update.message.reply_text(f"Оцениваем силу коупа от 1 до 6", quote=False)
        sleep(0.5)
        update.message.reply_dice(quote=False)
    elif res == 25:
        # Cope harder sir
        update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", quote=False)
    elif res == 26:
        update.message.reply_text(f"Врать не буду, коуп не впечатлил", quote=False)
    elif res == 27:
        update.message.reply_text(f"Удовлетворительный коуп", quote=False)
    elif res == 28:
        update.message.reply_text(f"Взорванный коуп!", quote=False)
    elif res == 29:
        update.message.reply_text(f"Хорош коупить, погнали лучше в казиныч!\nЗаодно посмотрим насколько хорошо твой коуп сможет выбить нам 3 лимона", quote=False)
        sleep(0.5)
        update.message.reply_dice(emoji="🎰", quote=False)
    elif res == 30:
        update.message.reply_text(f"Хорош коупить, погнали лучше в боулинг!\nЗаодно посмотрим насколько хорошо твой коуп умеет выбивать кегли", quote=False)
        sleep(0.5)
        update.message.reply_dice(emoji="🎳", quote=False)
    elif res == 31:
        update.message.reply_text(f"Хорош коупить, погнали лучше в дартс!\nЗаодно посмотрим насколько хорошо твой коуп попадает в яблочко!", quote=False)
        sleep(0.5)
        update.message.reply_dice(emoji="🎯", quote=False)
    elif res == 32:
        update.message.reply_text(f"Хорош коупить, погнали лучше в футбол!\nЗаодно посмотрим насколько хорошо твой коуп залетает в ворота", quote=False)
        sleep(0.5)
        update.message.reply_dice(emoji="⚽", quote=False)
    elif res == 33:
        update.message.reply_text(f"Хорош коупить, погнали лучше в баскетбол!\nЗаодно посмотрим насколько хорошо твой коуп залетает в корзину", quote=False)
        sleep(0.5)
        update.message.reply_dice(emoji="🏀", quote=False)



def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler("cope", random_cope))
    pass