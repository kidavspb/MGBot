import json


class UsersManager:
    def __init__(self):
        self.filename = "data/users.json"
        self.data = self.read_data()

    def read_data(self):
        with open(self.filename, 'r') as file:
            data = json.load(file)
            return {int(key): value for key, value in data.items()}

    def write_data(self):
        with open(self.filename, 'w') as file:
            json.dump(self.data, file, indent=2, ensure_ascii=False)

    def get_data(self):
        return self.data

    def increment(self, user_id, type, status=None):
        if status == "approved":
            self.data[user_id]["counter"][type]["approved"] += 1
        self.data[user_id]["counter"][type]["all"] += 1
        self.write_data()

    def add_new_user(self, user_id, username, phone_number):
        val = {
            "blocked": False,
            "username": username,
            "phone_number": phone_number,
            "counter": {
                "digital": {
                    "all": 0,
                    "approved": 0
                },
                "paper": {
                    "all": 0,
                    "approved": 0
                }
            }
        }
        self.data[user_id] = val
        self.write_data()

    def block_user(self, user_id, ):
        if user_id in self.data:
            self.data[user_id]["blocked"] = True
            self.write_data()
            return True
        return False

    def unblock_user(self, user_id, ):
        if user_id in self.data:
            self.data[user_id]["blocked"] = False
            self.write_data()
            return True
        return False

users_manager = UsersManager()
