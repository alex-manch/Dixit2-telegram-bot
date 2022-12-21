from config import TELEGRAM_TOKEN # importamos el token
from config import MI_CHAT_ID 
import telebot # para manejar la API de Telegram
import time
import threading
import random

import logging
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, PollHandler, PollAnswerHandler
from telegram.error import TelegramError, Unauthorized

import os
import sys
import traceback
import logging
import inspect

import classes

from img import IMG_msgs

TOKEN = TELEGRAM_TOKEN


PORT = int(os.environ.get("PORT", "8443"))

# Format is mmddyyyy
PATCHNUMBER = "03252020"

MIN_PLAYERS = 1

def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger
    
ERROR_LOGGER = setup_logger("error_logger", "error_logs.log")
INFO_LOGGER = setup_logger("info_logger", "info_logs.log")

# instanciamos el bot de Telegram
bot = telebot.TeleBot(TELEGRAM_TOKEN)

def static_handler(command):
    text = open("static_responses/{}.txt".format(command), "r", encoding="utf-8").read()

    return CommandHandler(command,
        lambda update, context: bot.send_message(chat_id=update.message.chat.id, text=text, parse_mode="html"))

def reset_chat_data(context):
    context.bot_data["is_game_pending"] = False
    context.bot_data["has_game_started"] = False
    context.bot_data["everyone_answered"] = False
    context.bot_data["voting_pending"] = False
    context.bot_data["pending_players"] = {}
    context.bot_data["game_obj"] = None
    context.bot_data["game_finished"] = False
    context.bot_data["randomized_ids"] = {}
    
def check_game_existence(game, chat_id):
    if game is None:
        text = open("static_responses/game_dne_failure.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        return False

    return True
    
def hola_handler(update, context):
    game = context.bot_data.get("game_obj")
    chat_id = update.message.chat.id

    if game is None and not context.bot_data.get("is_game_pending", False):
        reset_chat_data(context)
        context.bot_data["is_game_pending"] = True
        text = open("static_responses/new_game.txt", "r", encoding="utf-8").read()
    elif game is not None:
        text = open("static_responses/game_ongoing.txt", "r", encoding="utf-8").read()
    elif context.bot_data.get("is_game_pending", False):
        text = open("static_responses/game_pending.txt", "r", encoding="utf-8").read()
    else:
        text = "Ya se ha roto algo. ¿Qué has tocado?"

    bot.send_message(chat_id=chat_id, text=text)
    
def is_nickname_valid(name, user_id, context):
    if user_id in context.bot_data.get("pending_players", {}):
        if name.lower() == context.bot_data["pending_players"][user_id].lower():
            return True

    for id, user_name in context.bot_data.get("pending_players", {}).items():
        if name.lower() == user_name.lower():
            return False

    return True
    
def unirme_handler(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if not context.bot_data.get("is_game_pending", False):
        text = open("static_responses/join_game_not_pending.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    if context.args:
        nickname = " ".join(context.args)
    else:
        nickname = update.message.from_user.first_name

    if is_nickname_valid(nickname, user_id, context):
        context.bot_data["pending_players"][user_id] = nickname
        bot.send_message(chat_id=update.message.chat_id,
                         text="%s, te has unido a la partida.\nSi quieres cambiarte el nombre vuelve a poner /unirme [apodo]." % nickname)
        bot.send_message(chat_id=update.message.chat_id,
                         text="Número de jugadores actuales: %d" % len(context.bot_data.get("pending_players", {})))
        bot.send_message(chat_id=update.message.from_user.id,
                         text="%s, te has unido a la partida de Dixit2." % nickname)
    else:
        text = open("static_responses/invalid_nickname.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        
def mepiro_handler(update, context):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    if not context.bot_data.get("is_game_pending", False):
        text = open("static_responses/leave_game_not_pending_failure.txt", "r", encoding="utf-8").read()
    elif user_id not in context.bot_data.get("pending_players", {}):
        text = open("static_responses/leave_id_missing_failure.txt", "r", encoding="utf-8").read()
    else:
        text = "Te has ido de la partida."
        del context.bot_data["pending_players"][update.message.from_user.id]

    bot.send_message(chat_id=chat_id, text=text)
    
def listajugadores_handler(update, context):
    chat_id = update.message.chat_id
    text = "List of players: \n"
    game = context.bot_data.get("game_obj")

    if context.bot_data.get("is_game_pending", False):
        for user_id, name in context.bot_data.get("pending_players", {}).items():
            text += "%s\n" % name
    elif game is not None:
        for player in game.get_players().values():
            text += "%s\n" % player.get_name()
    else:
        text = open("static_responses/listplayers_failure.txt", "r", encoding="utf-8").read()

    bot.send_message(chat_id=chat_id, text=text)
    
def feedback_handler(update, context):
    if context.args and len(context.args) > 0:
        feedback = open("feedback.txt\n", "a+", encoding="utf-8")
        feedback.write(update.message.from_user.first_name + "\n")
        feedback.write(str(update.message.from_user.id) + "\n")
        feedback.write(" ".join(context.args) + "\n")
        feedback.close()
        bot.send_message(chat_id=update.message.chat_id, text="Gracias por el feedback.")
    else:
        bot.send_message(chat_id=update.message.chat_id, text="Uso: /feedback [feedback]")    

def comenzar_handler(update, context):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    pending_players = context.bot_data.get("pending_players", {})

    if not context.bot_data.get("is_game_pending", False):
        text = open("static_responses/start_game_not_pending.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    if user_id not in context.bot_data.get("pending_players", {}).keys():
        text = open("static_responses/start_game_id_missing_failure.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    if len(pending_players) < MIN_PLAYERS:
        text = open("static_responses/start_game_min_threshold.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    try:
        for user_id, nickname in pending_players.items():
            bot.send_message(chat_id=user_id, text="Cumenzando el juego.")
    except Unauthorized as u:
        text = open("static_responses/start_game_failure.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        return

    text = open("static_responses/start_game.txt", "r", encoding="utf-8").read()
    bot.send_message(chat_id=chat_id, text=text)

    chat_id = update.message.chat_id
    pending_players = context.bot_data.get("pending_players", {})
    context.bot_data["is_game_pending"] = False
    context.bot_data["has_game_started"] = True
    context.bot_data["game_obj"] = classes.Game(chat_id, pending_players, IMG_msgs)
    game = context.bot_data["game_obj"]
    
    #hacer un bucle que se repita si ningún jugador gana
    context.bot_data["everyone_answered"] = False
    game.next_turn()


# esto va a gestionar las respuestas al juego que no son comandos
def handle_every_message(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    pending_players = context.bot_data.get("pending_players", {})
    game = context.bot_data.get("game_obj")
    
    if not (context.bot_data.get("has_game_started", False) or context.bot_data.get("everyone_answered", False)):
        return
    
    if user_id not in context.bot_data.get("pending_players", {}).keys():
        bot.send_message(chat_id=chat_id, text="No estás en ninguna partida.")
        return
    
    if update.message.text.startswith("/"):
        bot.send_message(update.message.chat.id, "Lo siento. Ese comando no está definido. Pon /help si necesitas ayuda.")
    else:
        bot.reply_to(update.message, "Muy buena. Guardo tu respuesta.")
        context.bot_data["everyone_answered"] = game.play(user_id, update.message.text)
        text = "Jugadores que han respondido:\n"
        
        for user_id in context.bot_data["pending_players"]:
            if user_id in game.get_players_answered():
                text += "%s\n" % context.bot_data["pending_players"][user_id]
        for telegram_id in pending_players:
            bot.send_message(telegram_id, text)
        
        if context.bot_data["everyone_answered"]:
            print("Todo el mundo ha respondido!")
            #bot.send_message(MI_CHAT_ID, "pon /votar")
            votar_handler(update, context)

def votar_handler(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    pending_players = context.bot_data.get("pending_players", {})
    game = context.bot_data.get("game_obj")
    
    if context.bot_data.get("everyone_answered", False) and not context.bot_data.get("voting_pending", False):
        context.bot_data["voting_pending"] = True
        game.send_state()
        
        options = game.shuffle_answers()
        #print("options: ",options)
       
        answers = []
        for id, answer in options:
            answers += [answer]
        #print(answers)

        polls_id = []
        for telegram_id in pending_players:
            x = bot.send_poll(telegram_id, question="Tienes 60 segundos para votar", options=answers, is_anonymous= False, close_date=60)
            polls_id += [x.id]
        #print(polls_id)
    else:
        bot.send_message(chat_id, "Como diría Alfonso cuando no encuentra la pelota de basket: </i>Aún no se puede votar</i>.", parse_mode="html")
    return

def puntos_handler(update, context):
    game = context.bot_data.get("game_obj")
    pending_players = context.bot_data.get("pending_players", {})
    randomized_ids = game.get_randomized_ids()
    context.bot_data["randomized_ids"] = randomized_ids
    
    # votación de "jaja que sutil" #################
    for telegram_id in pending_players:
        answers = []
        for i, j in randomized_ids:
            if i != telegram_id: #quitar tu respuesta solo, y la original que no sume puntos a nadie y ya
                answers += [j]       
        bot.send_poll(telegram_id, question="puedes dar puntos: jaja que sutil", options=answers, is_anonymous=True, open_period=60, allows_multiple_answers=True)
        bot.send_message(telegram_id, "No olvides darle a <b>Votar</b>.", parse_mode="html")
    time.sleep(15)
    
    # enviamos la respuesta correcta
    for i, j in randomized_ids:
        if i == 0:
            respuesta_correcta = j
    text = "La <b>respuesta correcta</b> era:\n"
    text +=  respuesta_correcta
    for telegram_id in pending_players:
        bot.send_message(telegram_id, text, parse_mode="html")
    time.sleep(2)
    
    # sumamos a cada uno los puntos en función de lo que haya votado
    for user_id in pending_players:
        respuesta = game.get_players()[user_id].get_answer()
        if respuesta == 0:
            game.get_players()[user_id].increment_score(3)
            bot.send_message(user_id, "Enhorabuena! He oido que tu novia es... digo, has acertado!!")
        elif respuesta != user_id:
        #else:
            game.get_players()[respuesta].increment_score(1)
            text = "Te ha votado "
            text += context.bot_data["pending_players"][user_id]
            bot.send_message(respuesta, text)
    time.sleep(5)
    
    # sacamos la lista de puntuaciones
    game.send_scoreboard()
    time.sleep(10)
    
    # check for win
    winner = game.check_for_win()
    if not winner:
        context.bot_data["everyone_answered"] = False
        game.next_turn()

    else:
        for user_id in pending_players:
            bot.send_message(chat_id=user_id, text="¡%s ha ganado!" % winner)
        bot.send_message(MI_CHAT_ID,"pon /mecorri")
    return

# esta es para las encuestas a mensaje original
def poll_handler(update, context):
    game = context.bot_data.get("game_obj")
    pending_players = context.bot_data.get("pending_players", {})
    user_id = update.poll_answer.user.id   
    
    if context.bot_data.get("voting_pending", False): 
        voted_option = update.poll_answer.option_ids[0]
        ids=game.get_randomized_ids()
        game.get_players()[user_id].add_answer(ids[voted_option][0])
        context.bot_data["voting_pending"] = not game.check_if_everyone_voted()
        if not context.bot_data["voting_pending"]:
            print("Todo el mundo ha votado!")
            #bot.send_message(chat_id=MI_CHAT_ID, text="pon /puntos")
            puntos_handler(update, context)
    
    return
    
# esta es para las encuestas a jaja que sutil
def sutil_handler(update, context):
    game = context.bot_data.get("game_obj")
    if (context.bot_data.get("has_game_started", False)):
        answers = update.poll.options
        ret = []
        for answer in answers:
            if answer.voter_count == 1:
                ret += [answer.text]
        for i, j in  context.bot_data["randomized_ids"]:
            for answer in ret:
                if j == answer and i != 0:
                    game.get_players()[i].add_sutil()
        #game.send_sutilboard()
    return

#bot.send_message(MI_CHAT_ID, "pon /next")


def adios_handler(update, context):
    game = context.bot_data.get("game_obj")
    pending_players = context.bot_data.get("pending_players", {})
    user_id = update.message.from_user.id
    chat_id = update.message.chat.id

    if context.bot_data.get("is_game_pending", False):
        context.bot_data["is_game_pending"] = False
        text = open("static_responses/end_game.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        context.bot_data["has_game_started"] = False
        return

    if game is None:
        text = open("static_responses/game_dne_failure.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
        return
    
    if user_id not in game.get_players():
        text = open("static_responses/end_game_id_missing_failure.txt", "r", encoding="utf-8").read()
        bot.send_message(chat_id=chat_id, text=text)
    game.send_sutilboard()
    reset_chat_data(context)
    text = open("static_responses/end_game.txt", "r", encoding="utf-8").read()
    bot.send_message(chat_id=chat_id, text=text)

def handle_error(update, context):
    trace = "".join(traceback.format_tb(sys.exc_info()[2]))
    ERROR_LOGGER.warning("Telegram Error! %s with context error %s caused by this update: %s", trace, context.error, update)

# MAIN ############################################
if __name__ == '__main__':
    # Set up the bot
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Static command handlers
    static_commands = ["start", "reglas", "help"]
    for c in static_commands:
        dispatcher.add_handler(static_handler(c))

    # Main command handlers
    join_aliases = ["unirme"]
    leave_aliases = ["mepiro", "unjoin"]
    listplayers_aliases = ["listajugadores", "list"]
    feedback_aliases = ["feedback"]
    newgame_aliases = ["hola"]
    startgame_aliases = ["comenzar"]
    endgame_aliases = ["adios"]
    votar_aliases = ["votar"]
    puntos_aliases = ["puntos"]

    commands = [("feedback", feedback_aliases),
                ("hola", newgame_aliases),
                ("unirme", join_aliases),
                ("mepiro", leave_aliases),
                ("listajugadores", listplayers_aliases),
                ("comenzar", startgame_aliases),
                ("adios", endgame_aliases),
                ("votar", votar_aliases),
                ("puntos", puntos_aliases)]
    for base_name, aliases in commands:
        func = locals()[base_name + "_handler"]
        dispatcher.add_handler(CommandHandler(aliases, func))
    
    # Answers handlers
    dispatcher.add_handler(MessageHandler(Filters.text, handle_every_message))
    
    # Poll handlers
    dispatcher.add_handler(PollAnswerHandler(poll_handler))
    dispatcher.add_handler(PollHandler(sutil_handler))
    
    # Error handlers
    dispatcher.add_error_handler(handle_error)
    
    updater.start_polling()
    updater.idle()