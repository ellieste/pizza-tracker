#!/usr/bin/env python3
import requests
import time
import json
import os
import threading
import logging
import curses
import pygame
from datetime import datetime

#Setup logging for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG = {
    "check_interval": 10,
    "pizza_services": {
        "dominos": {
            "enabled": True,
            "base_url": "https://order.dominos.com/power/trackOrder",
            "tracking_params": {
                "store_id": "",
                "order_key": ""
            }
        },
        "pizza_hut": {
            "enabled": False,
            "base_url": "https://www.pizzahut.com/api/oh-yeah/track",
            "tracking_params": {
                "order_id": ""
            }
        },
        "papa_johns": {
            "enabled": False,
            "base_url": "https://www.papajohns.com/order/trackorder",
            "tracking_params": {
                "order_number": ""
            }
        }
    },
    "notification_distance": 0.0,
    "sound_file": "pizza_time.wav"
}

class PizzaTrackerTerminal:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.current_status = "Waiting for order info"
        self.delivery_eta = None
        self.is_delivered = False
        self.notification_played = False
        self.last_update_time = None
        self.progress = 0
        self.current_order = "Getting Order Info"



        curses.curs_set(0)  #Hide cursor
        curses.start_color()
        curses.use_default_colors()

        self.stdscr.nodelay(True)
        
        curses.init_pair(1, curses.COLOR_BLUE, -1)  #Blue
        curses.init_pair(2, curses.COLOR_GREEN, -1)  #Green
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  #Yellow/Orange
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  #Purple
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_CYAN)  #Progress Bar
        curses.init_pair(6, curses.COLOR_RED, -1) #Red

        self.height, self.width = stdscr.getmaxyx()
        
        self.running = True
        self.tracking_thread = threading.Thread(target=self.tracking_loop)
        self.tracking_thread.daemon = True
        self.tracking_thread.start()
    
    def draw_box(self, y, x, height, width):
        self.stdscr.addstr(y, x, "┌" + "─" * (width - 2) + "┐")
        
        for i in range(1, height - 1):
            self.stdscr.addstr(y + i, x, "│")
            self.stdscr.addstr(y + i, x + width - 1, "│")
    
        self.stdscr.addstr(y + height - 1, x, "└" + "─" * (width - 2) + "┘")
    
    def draw_horizontal_line(self, y, x, width):
        self.stdscr.addstr(y, x, "├" + "─" * (width - 2) + "┤")
    
    def update_display(self):
        try:
            #Clear screen
            self.stdscr.clear()
            
            #Get new terminal size
            self.height, self.width = self.stdscr.getmaxyx()
            
            #Draw main box
            box_width = min(60, self.width - 4)
            box_height = min(22, self.height - 2)
            start_x = (self.width - box_width) // 2
            start_y = (self.height - box_height) // 2
            
            self.draw_box(start_y, start_x, box_height, box_width)
            
            #Draw title
            title = "  Pizza Tracker  "
            title_x = start_x + (box_width - len(title)) // 2
            self.stdscr.addstr(start_y + 2, title_x, title, curses.color_pair(3))
            
            # Draw horizontal line
            self.draw_horizontal_line(start_y + 4, start_x, box_width)

            #Draw Order label and Order
            self.stdscr.addstr(start_y + 5, start_x + 2, "Order: ", curses.A_BOLD)
            self.stdscr.addstr(start_y + 6, start_x + 2, self.current_order, curses.color_pair(6))

            
            #Draw Status label and Status
            self.stdscr.addstr(start_y + 8, start_x + 2, "Current Status:", curses.A_BOLD)
            self.stdscr.addstr(start_y + 9, start_x + 2, self.current_status, curses.color_pair(1))
            
            #Draw ETA if available
            if self.delivery_eta:
                self.stdscr.addstr(start_y + 11, start_x + 2, "Estimated Delivery Time: ", curses.A_BOLD)
                self.stdscr.addstr(start_y + 11, start_x + 26, self.delivery_eta, curses.color_pair(2))
            
            #Draw progress bar label
            self.stdscr.addstr(start_y + 14, start_x + 2, "Delivery Progress:", curses.A_BOLD)
            
            #Draw progress bar
            bar_width = 40
            filled_width = int(bar_width * (self.progress / 100))
            
            #Draw the filled part
            progress_bar = "█" * filled_width + "░" * (bar_width - filled_width)
            self.stdscr.addstr(start_y + 15, start_x + 2, progress_bar)
            
            #Draw progress percentage
            self.stdscr.addstr(start_y + 15, start_x + bar_width + 4, f"{self.progress}%")
            
            if self.last_update_time:
                update_text = f"Last Updated: {self.last_update_time.strftime('%I:%M %p')}"
                self.stdscr.addstr(start_y + box_height - 2, 
                                 start_x + box_width - len(update_text) - 2,
                                 update_text)
            
            self.stdscr.addstr(start_y + box_height, start_x, "Press q to exit", curses.A_DIM)
            
            self.stdscr.refresh()
            
        except curses.error:
            pass
    
    def show_alert(self, message):
        try:
            self.stdscr.clear()
            self.stdscr.refresh()

            #Calculate alert box dimensions
            alert_height = 5
            alert_width = len(message) + 10
            alert_y = (self.height - alert_height) // 2
            alert_x = (self.width - alert_width) // 2
            
            #Draw alert box
            self.draw_box(alert_y, alert_x, alert_height, alert_width)
            
            #Display message
            self.stdscr.addstr(alert_y + 2, alert_x + 5, message, curses.A_BOLD | curses.color_pair(3))
            self.stdscr.addstr(alert_y + 6, alert_x + (alert_width - 23) // 2, "Press any key to dismiss", curses.A_DIM)

            self.stdscr.refresh()

            self.stdscr.nodelay(False)
            self.stdscr.getch()

        except curses.error:
            pass

        finally:
            self.stdscr.nodelay(True)

            self.stdscr.clear()

            #Redraw main screen
            try:
                self.update_display()
                self.stdscr.refresh()

            except curses.error:
                pass
    
    def check_dominos_status(self, store_id, order_key):
        try:
            url = f"{CONFIG['pizza_services']['dominos']['base_url']}?storeId={store_id}&orderKey={order_key}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            print(f"Trying to connect to: {url}")
            
            response = requests.get(url, headers=headers)
            
            print(f"Response status code: {response.status_code}")
            print(f"Response Content: {response.text[:100]}...")

            if response.status_code == 200:
                data = response.json()
                
                #Parse the Domino's status response
                if 'order' in data and 'orderStatus' in data['order']:
                    status = data['order']['orderStatus']
                    
                    #Status Mapping
                    status_mapping = {
                        "OrderPlaced": "Order received",
                        "OrderMaking": "Making your pizza",
                        "OrderBaking": "Baking your pizza",
                        "OrderSent": "Pizza is on its way!",
                        "OrderDelivered": "Pizza delivered!"
                    }
                    
                    #Progress percentage
                    progress_mapping = {
                        "OrderPlaced": 20,
                        "OrderMaking": 40,
                        "OrderBaking": 60,
                        "OrderSent": 80,
                        "OrderDelivered": 100
                    }
                    
                    self.current_status = status_mapping.get(status, f"Status: {status}")
                    self.progress = progress_mapping.get(status, 0)
                    
                    #Check for ETA
                    if 'estimatedDeliveryTime' in data['order']:
                        self.delivery_eta = data['order']['estimatedDeliveryTime']
                    
                    #Check for order
                    if 'orderDescription' in data['order']:
                        self.current_order = data['order']['orderDescription']
                    
                    #Check if delivered
                    if status == "OrderDelivered" and not self.is_delivered:
                        self.is_delivered = True
                        self.play_notification()
                    
                    #Update last check time
                    self.last_update_time = datetime.now()
                    return True
                
            logger.warning(f"Failed to get status. Status code: {response.status_code}")
            return False
            
        except Exception as e:
            import traceback
            print(f"Error checking Dominos status: {e}")
            print(traceback.format_exc())
            logger.error(f"Error checking Domino's status: {e}")
            self.current_status = "Error checking status"
            return False
    
    def check_pizza_hut_status(self, order_id):
        self.current_status = "Pizza Hut tracking not implemented"
        return False
    
    def check_papa_johns_status(self, order_number):
        self.current_status = "Papa John's tracking not implemented"
        return False
    
    def check_status(self):
        status_checked = False
        
        if CONFIG["pizza_services"]["dominos"]["enabled"]:
            params = CONFIG["pizza_services"]["dominos"]["tracking_params"]
            if params["store_id"] and params["order_key"]:
                status_checked = self.check_dominos_status(
                    params["store_id"], 
                    params["order_key"]
                )
        
        if not status_checked and CONFIG["pizza_services"]["pizza_hut"]["enabled"]:
            params = CONFIG["pizza_services"]["pizza_hut"]["tracking_params"]
            if params["order_id"]:
                status_checked = self.check_pizza_hut_status(params["order_id"])
        
        if not status_checked and CONFIG["pizza_services"]["papa_johns"]["enabled"]:
            params = CONFIG["pizza_services"]["papa_johns"]["tracking_params"]
            if params["order_number"]:
                status_checked = self.check_papa_johns_status(params["order_number"])
    
    def play_notification(self):
        self.notification_played = True
        self.show_alert("IT'S PIZZA TIME!")
    
    def tracking_loop(self):
        logger.info("Starting pizza tracking")
        last_check_time = 0

        try:
            while self.running:
                current_time = time.time()

                if current_time - last_check_time >= CONFIG["check_interval"]:
                   self.check_status()
                   last_check_time = current_time

                   with open('debug.log', 'a') as f:
                       f.write(f"Checked at {datetime.now().strftime('%H:%M:%S')}: {self.current_status}\n")

                self.update_display()
                
                try:
                    key = self.stdscr.getch()
                    if key == ord('q'):
                        self.running = False
                except:
                    pass
                
                time.sleep(0.1)
                
        except Exception as e:
            import traceback
            with open('debug.log', 'a') as f:
                f.write(f"Error in tracking loop: {e}\n")
                f.write(traceback.format_exc())
            logger.error(f"Error in tracking loop: {e}")

def load_config():
    global CONFIG
    config_file = os.path.join(os.path.dirname(__file__), 'pizza_config.json')
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
                CONFIG.update(loaded_config)
            logger.info("Configuration loaded from pizza_config.json")

            sound_file = CONFIG["sound_file"]
            if not os.path.exists(sound_file):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                alt_sound_path = os.path.join(script_dir, sound_file)
                if os.path.exists(alt_sound_path):
                    CONFIG["sound_file"] = alt_sound_path
                    logger.info(f"Sound file found at {alt_sound_path}")
                else:
                    logger.warning(f"Sound file not found: {sound_file}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")


def setup_config():
    print("\n==== Pizza Tracker Setup ====")
    print("Which pizza service are you ordering from?")
    print("1. Domino's Pizza")
    print("2. Pizza Hut")
    print("3. Papa John's")
    print("4. Domino's Pizza (Local Test Server)")
    
    choice = input("Enter your choice (1-4): ")
    
    for service in CONFIG["pizza_services"]:
        CONFIG["pizza_services"][service]["enabled"] = False
    
    if choice == "1":
        CONFIG["pizza_services"]["dominos"]["enabled"] = True
        store_id = input("Enter the Domino's store ID: ")
        order_key = input("Enter the order key: ")
        CONFIG["pizza_services"]["dominos"]["tracking_params"]["store_id"] = store_id
        CONFIG["pizza_services"]["dominos"]["tracking_params"]["order_key"] = order_key
        
    elif choice == "2":
        CONFIG["pizza_services"]["pizza_hut"]["enabled"] = True
        order_id = input("Enter the Pizza Hut order ID: ")
        CONFIG["pizza_services"]["pizza_hut"]["tracking_params"]["order_id"] = order_id
    
    elif choice == "3":
        CONFIG["pizza_services"]["papa_johns"]["enabled"] = True
        order_number = input("Enter the Papa John's order number: ")
        CONFIG["pizza_services"]["papa_johns"]["tracking_params"]["order_number"] = order_number
        
    elif choice == "4":
        CONFIG["pizza_services"]["dominos"]["enabled"] = True
        CONFIG["pizza_services"]["dominos"]["base_url"] = "http://localhost:5000/power/trackOrder"
        CONFIG["pizza_services"]["dominos"]["tracking_params"]["store_id"] = "1234"
        CONFIG["pizza_services"]["dominos"]["tracking_params"]["order_key"] = "ABCD1234"
        print("Configured for local test server with default test credentials")
    
    else:
        print("Invalid choice. Using default configuration.")
    
    #Save configuration
    with open('pizza_config.json', 'w') as f:
        json.dump(CONFIG, f, indent=4)
    
    print("Configuration saved to pizza_config.json")


def main():
    load_config()
    setup_config()
    
    
    #Start the terminal UI
    try:
        curses.wrapper(lambda stdscr: run_tracker(stdscr))
    except KeyboardInterrupt:
        logger.info("Pizza tracking stopped by user")


def run_tracker(stdscr):

    tracker = PizzaTrackerTerminal(stdscr)
    
    while tracker.running:
        time.sleep(0.1)
    
    curses.endwin()


if __name__ == "__main__":
    main()
