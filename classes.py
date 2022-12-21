from __future__ import unicode_literals
from config import TELEGRAM_TOKEN# importamos el token

from collections import defaultdict
import telegram
from telegram.error import Unauthorized, TelegramError
import os.path

import random
#from img import IMG_msgs

TOKEN = TELEGRAM_TOKEN
bot = telegram.Bot(token=TOKEN)

# definimos los jugadores y sus propiedades
class Player:
    def __init__(self, name, answer):
        self.__answer = answer
        self.__name = name
        self.__score = 0
        self.__sutil = 0

    def get_name(self):
        return self.__name
    
    def add_answer(self, text):
        self.__answer = text
        if text != "":
            print(self.__name, " ha votado ", self.__answer)
    
    def get_answer(self):
        return self.__answer

    def get_score(self):
        return self.__score
        
    def get_sutil(self):
        return self.__sutil
    
    def add_sutil(self):
        self.__sutil += 1

    def increment_score(self, points):
        self.__score += points
        

class IMGS:
    def __init__(self, imgs_to_use):
        self.__IMG_srcs = []
        self.__IMG_msgs = imgs_to_use
        for n in range(len(self.__IMG_msgs)):
            self.__IMG_srcs.append("./img/"+str(n)+".jpg")
        
        c = list(zip(self.__IMG_msgs, self.__IMG_srcs))
        random.shuffle(c)
        self.__IMG_msgs, self.__IMG_srcs = zip(*c)

    def draw_image(self):
        print(len(self.__IMG_srcs))
        if len(self.__IMG_srcs) > 0:
            result = self.__IMG_srcs[0]
            self.__IMG_srcs = self.__IMG_srcs[1:len(self.__IMG_srcs)]
        else:
            result = []
        return result
    
    def draw_msg(self):
        print(len(self.__IMG_srcs))
        if len(self.__IMG_msgs) > 0:
            result = self.__IMG_msgs[0]
            self.__IMG_msgs = self.__IMG_msgs[1:len(self.__IMG_msgs)]
        else:
            print("me he quedado sin fotos")
            result = "me he quedado sin fotos"
        return result

# definimos el juego y sus propiedades
class Game:
    def __init__(self, chat_id, players, imgs_to_use):
        self.__turn = 0
        # Players is a dict of (Telegram ID, name).
        self.__players = {}
        self.__imgs = IMGS(imgs_to_use)
        self.__chat_id = chat_id
        self.__current_img_src = []
        self.__current_img_msg = []
        # This is a dict of (Telegram ID, list of cards submitted).
        self.__answers_submitted_this_round = defaultdict(list)
        self.__randomized_ids = []
        # Whoever gets to 30 points first wins!
        self.__WIN_NUM = 30
        
        player_keys = list(players.keys())
        random.shuffle(player_keys)
        for id in player_keys:
            self.__players[id] = Player(players[id], "")
            #self.send_message(self.__chat_id, "%s has been added to the game.\n" % players[id])
        
        #self.send_state()    
    
    def get_players(self):
        return self.__players
    
    def get_randomized_ids(self):
        return self.__randomized_ids
    
    def get_img_src(self):
        return __current_img_src
        
    def get_img_msg(self):
        return __current_img_msg
        
    def send_state(self):
        img_text="¿Con qué texto se mandó esta imagen?"
        if os.path.exists(self.__current_img_src):
            for telegram_id in self.__players.keys():
                foto = open(self.__current_img_src, "rb")
                bot.send_photo(telegram_id, foto, img_text)
        else:
            print("No se ha encontrado la foto")
            img_text="No se ha encontrado la foto"
            for telegram_id in self.__players.keys():
                foto = "https://assets.hongkiat.com/uploads/funny_error_messages/ok-button-to-continue-funny-error-messages.jpg?newedit"
                bot.send_photo(telegram_id, foto, img_text)
            

    def next_turn(self):
        self.__current_img_msg = self.__imgs.draw_msg()
        if self.__current_img_msg != "me he quedado sin fotos":
            self.__current_img_src = self.__imgs.draw_image()
        else:
            print("pues si te has quedado sin fotos, acaba el juego ya")
            for telegram_id in self.__players.keys():
                bot.send_message(telegram_id, "Me he quedado sin fotos.", parse_mode=telegram.ParseMode.HTML)
            self.send_scoreboard()
            return
        self.__randomized_ids = []
        self.__answers_submitted_this_round = defaultdict(list) #borrar todas las respuestas anteriores
        for id in self.__players.keys(): 
            self.__players[id].add_answer("")

        self.send_state()
        
        #return  self.__current_img_msg

    def check_for_win(self):
        for p in self.__players.values():
            if p.get_score() >= self.__WIN_NUM:
                return p.get_name()
        return False
   
    def check_if_everyone_answered(self):
        return len(self.__answers_submitted_this_round.keys()) == len(self.__players) #and \
                #all(len(answer) == self.__current_black_card[0] for cards in self.__cards_submitted_this_round.values())
        
    def play(self, telegram_id, answer_txt):
        player = self.__players[telegram_id]
        if player is None:
            self.send_message(self.__chat_id, "No pareces existir.")
            return   
        self.__answers_submitted_this_round[telegram_id] = answer_txt # añado la respuesta a la lista de respuestas  
        
        return self.check_if_everyone_answered()

    def shuffle_answers(self):
        self.__answers_submitted_this_round[0] = self.__current_img_msg
        self.__randomized_ids = list(self.__answers_submitted_this_round.items())
        random.shuffle(self.__randomized_ids)
        return self.__randomized_ids

    def get_answers(self):
        return self.__answers_submitted_this_round

    def get_current_msg(self):
        return self.__current_img_msg
    
    def get_players_answered(self):
        players = self.__players
        for player in players:
            if not self.__answers_submitted_this_round[player]:
                players.remove(player)
        return players

    def check_if_everyone_voted(self):
        i = 0
        for id in self.__players:
            if self.__players[id].get_answer() != "":
                i += 1
        return i == len(self.__players)

    def send_scoreboard(self):
        text = "<b>Puntuaciones:</b>\n\n"
        for p in self.__players.values():
            text += "%s: %s\n" % (p.get_name(), p.get_score())
        for telegram_id in self.__players.keys():
            bot.send_message(telegram_id, text, parse_mode=telegram.ParseMode.HTML)

    def send_sutilboard(self):
        text = "<b>Puntuaciones a <i>jaja que sutil</i>:</b>\n\n"
        for p in self.__players.values():
            text += "%s: %s\n" % (p.get_name(), p.get_sutil())
        for telegram_id in self.__players.keys():
            bot.send_message(telegram_id, text, parse_mode=telegram.ParseMode.HTML)