from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler
import random
import asyncio
import logging
from getval import send_val, vals_of_type, all_keys, get_val, TYPE_GIF, TYPE_STICKER
from opinion import opinion
from utils import CommandTrigger

logger = logging.getLogger(__name__)

async def random_cope(update: Update, context: CallbackContext):
    options = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33]
    weights = [100, 100, 100, 100, 60, 0.1, 100, 4, 50, 15, 3, 3, 40, 15, 20, 1, 6, 6, 6, 1.5, 1.5, 35, 20, 90, 50, 90, 100, 12, 1, 0.5, 0.5, 0.5, 0.5]
    res = random.choices(options, weights=weights)[0]
    logger.info(f"[cope] res {res}")
    if res == 1:
        await update.message.reply_text(f"Найс коупишь", do_quote=False)
    elif res == 2:
        await update.message.reply_text(f"Коуп жиденький", do_quote=False)
    elif res == 3:
        await update.message.reply_text(f"Коуп хороший\nЗдорово покоупил", do_quote=False)
    elif res == 4:
        await update.message.reply_text(f"Коуп плохой\nКоупи лучше", do_quote=False)
    elif res == 5:
        await update.message.reply_text(f"Коуп отвратительный", do_quote=False)
    elif res == 6:
        await update.message.reply_text(f"=== ЛЕГЕНДАРНЫЙ КОУП ===\nЭтот коуп войдет в историю!\nПоздравляем @{update.message.from_user.username} с получением этого невероятного редкого коупа", do_quote=False)
    elif res == 7:
        await update.message.reply_text(f"Коуп слабый\nКоупи сильнее", do_quote=False)
    elif res == 8:
        await update.message.reply_text(f"Тариф Гигакоупище\nБезлимитный коуп по всей России", do_quote=False)
    elif res == 9:
        await update.message.reply_text(f"Лютейший коуп", do_quote=False)
    elif res == 10:
        await update.message.reply_text(f"Удачный коуп!\nМожешь еще раз покоупить", do_quote=False)
    elif res == 11:
        await update.message.reply_text(f"Этот божественный коуп настолько силен, что способен излучать ауру добра и позитива, которая увеличивает силу коупа друзей на 50%", do_quote=False)
    elif res == 12:
        await update.message.reply_text(f"Выбираем главного коупера дня", do_quote=False)
        await asyncio.sleep(1.5)
        await update.message.reply_text(random.choice(["Хмм...", "Так-так-так...", "Расшифровываю результаты...", "Спрашиваем мнения экспертов...", "Дайте подумать..."]), do_quote=False)
        await asyncio.sleep(1.5)
        await update.message.reply_text(f"А вот и победитель - @{update.message.from_user.username}!", do_quote=False)
    elif res == 13:
        await update.message.reply_text(f"Как же он сильно коупит...\nПарень полегче!", do_quote=False)
    elif res == 14:
        await update.message.reply_text(f"Критически плохой коуп!\nУ тебя весь день будет ФОМО", do_quote=False)
    elif res == 15:
        await update.message.reply_text(f"Отличный коуп!\nВсе проблемы решены", do_quote=False)
    elif res == 16:
        await update.message.reply_text(f"Шедевральный коуп!\nО нем напишут в книгах", do_quote=False)
    elif res == 17:
        await update.message.reply_text(f"Я не вижу вашего коупа", do_quote=False)
    elif res == 18:
        vals = vals_of_type(TYPE_STICKER)
        if len(vals) == 0:
            await update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", do_quote=False)
            return
        file_id = random.choice(vals).data
        logger.info(f"fileid {file_id}")
        await update.message.reply_sticker(file_id, do_quote=False)
    elif res == 19:
        vals = vals_of_type(TYPE_GIF)
        if len(vals) == 0:
            await update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", do_quote=False)
            return
        file_id = random.choice(vals).data
        logger.info(f"fileid {file_id}")
        await update.message.reply_animation(file_id, do_quote=False)
    elif res == 20:
        await update.message.reply_text(f"Кто-то сомневается в твоем коупе? Вызови его на дуэль в /rockpaperscissors и посмотри чей коуп победит!", do_quote=False)
    elif res == 21:
        await update.message.reply_text(f"Кто-то сомневается в твоем коупе? Вызови его на дуэль в /connectfour и посмотри чей коуп победит!", do_quote=False)
    elif res == 22:
        keys = [key for key in all_keys() if key.lower().startswith("коуп")]
        if len(keys) == 0:
            await update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", do_quote=False)
            return
        key = random.choice(keys)
        await update.message.reply_text(f"/get {key}", do_quote=False)
        await asyncio.sleep(0.5)
        logger.info(f"cope get {key}")
        val = get_val(key)
        await send_val(update.get_bot(), CommandTrigger.from_update(update), key, val, show_header=True)
    elif res == 23:
        await opinion(update, context, "коуп")
    elif res == 24:
        await update.message.reply_text(f"Оцениваем силу коупа от 1 до 6", do_quote=False)
        await asyncio.sleep(0.5)
        await update.message.reply_dice(do_quote=False)
    elif res == 25:
        # Cope harder sir
        await update.message.reply_animation("CgACAgQAAx0CT_IhJQABBXMmY7qlHgn9TsIE04UL3TKhfZGCmOgAAmIDAAJ43PVSPgZ0f8U9qU4tBA", do_quote=False)
    elif res == 26:
        await update.message.reply_text(f"Врать не буду, коуп не впечатлил", do_quote=False)
    elif res == 27:
        await update.message.reply_text(f"Удовлетворительный коуп", do_quote=False)
    elif res == 28:
        await update.message.reply_text(f"Взорванный коуп!", do_quote=False)
    elif res == 29:
        await update.message.reply_text(f"Хорош коупить, погнали лучше в казиныч!\nЗаодно посмотрим насколько хорошо твой коуп сможет выбить нам 3 лимона", do_quote=False)
        await asyncio.sleep(0.5)
        await update.message.reply_dice(emoji="🎰", do_quote=False)
    elif res == 30:
        await update.message.reply_text(f"Хорош коупить, погнали лучше в боулинг!\nЗаодно посмотрим насколько хорошо твой коуп умеет выбивать кегли", do_quote=False)
        await asyncio.sleep(0.5)
        await update.message.reply_dice(emoji="🎳", do_quote=False)
    elif res == 31:
        await update.message.reply_text(f"Хорош коупить, погнали лучше в дартс!\nЗаодно посмотрим насколько хорошо твой коуп попадает в яблочко!", do_quote=False)
        await asyncio.sleep(0.5)
        await update.message.reply_dice(emoji="🎯", do_quote=False)
    elif res == 32:
        await update.message.reply_text(f"Хорош коупить, погнали лучше в футбол!\nЗаодно посмотрим насколько хорошо твой коуп залетает в ворота", do_quote=False)
        await asyncio.sleep(0.5)
        await update.message.reply_dice(emoji="⚽", do_quote=False)
    elif res == 33:
        await update.message.reply_text(f"Хорош коупить, погнали лучше в баскетбол!\nЗаодно посмотрим насколько хорошо твой коуп залетает в корзину", do_quote=False)
        await asyncio.sleep(0.5)
        await update.message.reply_dice(emoji="🏀", do_quote=False)



def subscribe(a: Application):
    a.add_handler(CommandHandler("cope", random_cope))
    pass
