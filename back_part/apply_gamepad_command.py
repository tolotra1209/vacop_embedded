import json

def on_mqtt_message(self, client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))

        throttle = float(data["vector"]["throttle"])
        steering = float(data["vector"]["steering"])

        self.apply_gamepad_command(throttle, steering)

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[MQTT] Message invalide : {e}")

        
def apply_gamepad_command(self, throttle: float, steering: float):

    if throttle > 0:
        self.motors.set_forward()
    elif throttle < 0:
        self.motors.set_reverse()
    
    torque = abs(throttle) * 8.0
    self.motors.set_torque(torque)

    steering_target = int((steering + 1.0) / 2.0 * 1023)

    steering_target = max(0, min(1023, steering_target))

    self.steer.set_target(steering_target)
