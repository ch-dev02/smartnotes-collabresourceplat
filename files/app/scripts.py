import json

def valid_password(password):
    if len(password) < 8:
        return False

    if len(password) > 100:
        return False

    if not any(char.isdigit() for char in password):
        return False
         
    if not any(char.isupper() for char in password):
        return False
         
    if not any(char.islower() for char in password):
        return False

    if not any(char in "!@#$%^&*()_+-=[];:,./?" for char in password):
        return False

    return True
    
def allowed_file(filename, extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in extensions

class Node:
    def __init__(self, value: str, resources: list):
        self.value = value
        self.resources = resources
        self.left = None
        self.right = None

class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, value: str, resources: list):
        new_node = Node(value, resources)
        if self.root is None:
            self.root = new_node
        else:
            self._insert_helper(self.root, new_node)

    def _insert_helper(self, current: Node, new_node: Node):
        if new_node.value < current.value:
            if current.left is None:
                current.left = new_node
            else:
                self._insert_helper(current.left, new_node)
        elif new_node.value > current.value:
            if current.right is None:
                current.right = new_node
            else:
                self._insert_helper(current.right, new_node)
        else:
            return  # no duplicates allowed

    def find(self, value: str):
        if self.root is None:
            return None
        else:
            return self._find_helper(self.root, value)

    def _find_helper(self, current: Node, value: str):
        if current is None:
            return None
        elif current.value == value:
            return current
        elif value < current.value:
            return self._find_helper(current.left, value)
        else:
            return self._find_helper(current.right, value)

    def encode_json(self):
        return json.dumps(self._encode_json_helper(self.root))

    def _encode_json_helper(self, current: Node):
        if current is None:
            return None
        else:
            return {
                "value": current.value,
                "resources": current.resources,
                "left": self._encode_json_helper(current.left),
                "right": self._encode_json_helper(current.right)
            }

    def decode_json(self, json_data: str):
        if json_data is None or json_data == "":
            return
        else:
            self.root = self._decode_json_helper(json.loads(json_data))

    def _decode_json_helper(self, json_data: dict) -> Node:
        if json_data is None or json_data == "":
            return None
        else:
            node = Node(json_data["value"], json_data["resources"])
            node.left = self._decode_json_helper(json_data["left"])
            node.right = self._decode_json_helper(json_data["right"])
            return node
