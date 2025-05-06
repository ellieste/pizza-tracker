#!/usr/bin/env python3

from flask import Flask, jsonify, request
import time
import threading
import random
from datetime import datetime, timedelta

app = Flask(__name__)

#Global variables
ORDER_STATUS = "OrderPlaced"
START_TIME = datetime.now()
DELIVERY_TIME = START_TIME + timedelta(minutes=30)
DELIVERY_DISTANCE = 2.0  # miles
ORDER_DESCRIPTION = "1x Large Pepperoni Pizza, 1x Garlic Bread, 1x Large Coke"

STATUS_TIMINGS = {
    "OrderPlaced": 10,
    "OrderMaking": 10,
    "OrderBaking": 10,
    "OrderSent": 10,
    "OrderDelivered": -1
}

STATUS_SEQUENCE = ["OrderPlaced", "OrderMaking", "OrderBaking", "OrderSent", "OrderDelivered"]

def update_status_loop():
    global ORDER_STATUS, DELIVERY_DISTANCE
    
    current_status_index = 0
    
    while True:
        current_status = STATUS_SEQUENCE[current_status_index]
        wait_time = STATUS_TIMINGS[current_status]
        
        if current_status == "OrderDelivered":
            DELIVERY_DISTANCE = 0.0
            time.sleep(10)
            continue
            
        time.sleep(wait_time)
        
        current_status_index = min(current_status_index + 1, len(STATUS_SEQUENCE) - 1)
        ORDER_STATUS = STATUS_SEQUENCE[current_status_index]
        
        if ORDER_STATUS == "OrderSent":
            decrease_distance_thread = threading.Thread(target=decrease_distance)
            decrease_distance_thread.daemon = True
            decrease_distance_thread.start()

def decrease_distance():
    global DELIVERY_DISTANCE
    
    while DELIVERY_DISTANCE > 0:
        DELIVERY_DISTANCE = max(0, DELIVERY_DISTANCE - random.uniform(0.1, 0.5))
        
        time.sleep(10) #Update every 15 sec

@app.route('/power/trackOrder', methods=['GET'])
def track_dominos_order():
    """Mock Domino's Pizza tracking API."""
    store_id = request.args.get('storeId', '')
    order_key = request.args.get('orderKey', '')
    
    status = ORDER_STATUS
    
    eta = DELIVERY_TIME.strftime(" %I:%M %p")

    order = ORDER_DESCRIPTION
    response = {
        "order": {
            "orderStatus": status,
            "estimatedDeliveryTime": eta,
            "deliveryDistance": str(round(DELIVERY_DISTANCE, 2)),
            "orderDescription": order,
            "storeId": "1234" if not store_id else store_id,
            "orderKey": "ABCD1234" if not order_key else order_key
        },
        "status": 200,
        "success": True
    }
    
    return jsonify(response)

@app.route('/reset', methods=['GET'])
def reset_order():
    """Reset the order to its initial state."""
    global ORDER_STATUS, START_TIME, DELIVERY_TIME, DELIVERY_DISTANCE
    
    ORDER_STATUS = "OrderPlaced"
    START_TIME = datetime.now()
    DELIVERY_TIME = START_TIME + timedelta(minutes=30)
    DELIVERY_DISTANCE = 2.0
    
    return jsonify({"status": "Order reset successfully"})

@app.route('/status', methods=['GET'])
def get_status():
    """Get the current order status."""
    return jsonify({
        "orderStatus": ORDER_STATUS,
        "deliveryDistance": DELIVERY_DISTANCE,
        "estimatedDeliveryTime": DELIVERY_TIME.strftime("%I:%M %p")
    })

@app.route('/set_status', methods=['GET'])
def set_status():
    """Manually set the order status (for testing)."""
    global ORDER_STATUS
    
    status = request.args.get('status', '')
    if status in STATUS_SEQUENCE:
        ORDER_STATUS = status
        return jsonify({"status": f"Order status set to {status}"})
    else:
        return jsonify({"error": f"Invalid status. Valid statuses are: {', '.join(STATUS_SEQUENCE)}"}), 400

@app.route('/set_distance', methods=['GET'])
def set_distance():
    """Manually set the delivery distance (for testing)."""
    global DELIVERY_DISTANCE
    
    try:
        distance = float(request.args.get('distance', ''))
        DELIVERY_DISTANCE = max(0, min(distance, 5))
        return jsonify({"status": f"Delivery distance set to {DELIVERY_DISTANCE} miles"})
    except:
        return jsonify({"error": "Invalid distance. Must be a number."}), 400

if __name__ == '__main__':
    status_thread = threading.Thread(target=update_status_loop)
    status_thread.daemon = True
    status_thread.start()
    
    app.run(host='0.0.0.0', port=5000)
